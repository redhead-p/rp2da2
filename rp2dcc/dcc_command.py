"""DCC module
    :author: Paul Redhead

This module provides high level APIs. It and associated modules in the
package contain the functions and classes for DCC command station.

A command comprises a preamble, one or more instruction/data bytes and
an error detection (checksum) byte. Each byte is preceeded by a single '0' bit.
The checksum is followed by a single '1' bit which may be the initial bit of
the next preamble. The preamble is at least 14 '1' bits. Note that in this
implementation the pre-amble is not interrupted by the cutout so the preamble
length doesn't need to be lengthened.

This DCC implementation has a limited set of features.  E.g. it doesn't include
bit stretching for DC vehicles on address 0, 14/28 speed steps, any service mode
functions or accessory controller commands. We allow for a maximum command
sequnece of 11 bytes including check sum. There is limited support for
Programming on Main.

RCN-210 &  RCN-211 partly apply as appropriate. 

See also NMRA Standards S 9.2 and S 9.2.1. S 9.2.1.1 is not supported.

The module makes full use of a RP2xxx PIO for DCC signal encoding and
serialisation. If RailCom is enabled a second PIO is used for this. 

The DCC commands are serialised to the track via the DCC generation driver,
which also inserts the RailCom cutout if in use.

Three RP2040 PIO state machines are used by driver modules, one for DCC
generation and two for RailCom. The two RailCom state machines must be
on the same PIO block. 
"""
"""        Copyright (C) 2023, 2024, 2025, 2026 Paul Redhead

        This program is free software: you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the Free Software Foundation, 
        either version 3 of the License, or (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
        See the GNU General Public License for more details.
        You should have received a copy of the GNU General Public License along with this program.
        If not, see <http://www.gnu.org/licenses/>.
"""
import asyncio

from micropython import const
from machine import Pin

from hw_conf import HwConf
from dcc_cmd_util import SpeedCommand, FGrp1Command, CommandPacket, IdlePacket, CV_Access
from dcc_cmd_pio import DCCCmdTx


class DCCCommand():
    """ DCC Command

    This class manages the DCC command packets. It provides the APIs for the
    registration of DCC commands to be serialised. It performs the scheduling
    and tranmission of command packets.

    Attributes:
        FWD:    Forward direction
        REV:    Reverse direction
        STOP:   Stopped N.B this is included for completeness
        ON:     Power On
        OFF:    Power Off
    """

    # class constants - may be imported by other modules
    FWD = const(1)
    REV = const(-1)
    STOP = const(0)

    # used for both power and decoder functions
    ON = const(1)
    OFF = const(0)

    _dcc_cmd = None # singleton dcc command instance

    @classmethod
    def get_instance(cls):
        """ Get the DCC Command instance.

        This returns the singleton DCC Command instance.
        It instantiates DCC Command on the first call.

        Returns:
            The DCC Command instance
        """
        if cls._dcc_cmd is None:
            DCCCommand()
        return cls._dcc_cmd

    def __init__(self):
        """DCC Command object constructor
        
        This initialises the DCC command manager singleton.  An attempt to create a 2nd
        instance will cause an assertion error.
        
        The dictionary for the packet list is created and the 
        FIFO buffer allocated.

        """
        assert DCCCommand._dcc_cmd is None, 'Attempt to create 2nd DCC Cmd'
        DCCCommand._dcc_cmd = self

        # The packet list is used for commands that are currently scheduled for 
        # transmission. Speed & function commands are never deleted but POM commands have
        # limitied life span 
        self._packet_list = {}              # create empty dictionary
        self._counts = {}        # counts of issued commands by type
        self._pom_packet = None             # and no outstanding pom command
        # instantiate dcc generator
        self._dcc_gen_pio = DCCCmdTx.get_instance()
 
        self._idle_packet = IdlePacket()    # create an idle packet

        self._active_address = set() # acive mobile decoders

        # Set up interrupt on enable pin to schedule next packet when 
        # cutout period ends.
        HwConf.get_instance().dcc_pins[0].irq(self._nxt_packet, Pin.IRQ_RISING)

        self._ready_flag = asyncio.ThreadSafeFlag()

    @property
    def counts(self):
        """Get the command counts

        This returns the counts of commands sent by type. The counts are reset by the
        reset_counts method.

        Returns:
            A dictionary of command counts by type.
        """
        return self._counts

    def reset_counts(self):
        """Reset the command counts 

        This resets the command counts to zero. It is used to reset the command counts
        after a report has been printed.
        """
        self._counts = {}

    async def wait_for_flag(self):
        """ Wait for the new state available flag

        This waits for the asynchio thread safe flag to be set. Setting the flag is
        triggered by a change to the power on/off status.
        """
        await self._ready_flag.wait()
        return

    def power(self, p = None):
        """DCC Power On/Off

        Start and stop command packet transmission scheduling.
        PIO stop start and power to track delegated to the DCC tx class (pio_pwr).

        Changing the power state will cause the new power state available flag to be set.
        
        args:
            p: 1 for power on, 0 for power off, None for get power status

        returns:
            power status as held by the DCC generator
        """
        if p is None:
            # power is none
            return self._dcc_gen_pio.pio_pwr()
        # an explicit command always generates a response
        self._ready_flag.set()

        if p == self._dcc_gen_pio.pio_pwr():
            # but don't do anything if no change!
            return
        
        r = self._dcc_gen_pio.pio_pwr(p)  # start/stop pio first (before send!)

        if p == DCCCmdTx.ON:
            # the normal sequence of command packets will be triggered
            # at the completion of the idle packet
            self._dcc_gen_pio.pio_send(self._idle_packet)
            # set an iterator
            self._packet_iter = iter(self._packet_list)

        # no specific action here for power off
        return r

    def set_speed(self, address, dir, speed = 0):
        """Set Speed (including direction)
        
        If there is a speed command object for the adressed decoder in the
        list already the object is updated otherwise a new speed command
        is created.  The input is validated.  The packet generated will be
        for a 128 step speed setting and
        decoders must be configured for 28/128 speed steps.

        See NMRA S-9.2.1  Section 2.3.2.1
        
        args:
            address: the address of the decoder - may be short or long
            dir:    the direction - forward or reverse - stop is treated as invalid
            speed: the speed to be set - range 0 to 127 - default 0
              
        returns:
            True if validation is passed and the command is added to the list
            or modified. False if validation fails.
        """
        # a bit of defensive programming
        if not (1 <= address <= CommandPacket.MAX_LONG_ADDR):
            return False
        if not dir in (DCCCommand.FWD, DCCCommand.REV):
            return False
        if not (0 <= speed < 128):
            return False
        
        # speed direction packet list entry's key is 'S', address
        # speed / direction packet - 1 or 2 address bytes, 2 instruction bytes  
        try:
            self._get_cmd((SpeedCommand.TYPE, address)).update(dir, speed)
        except KeyError:
            self._add_cmd(SpeedCommand(address, dir, speed))

        return True

    def set_fg1(self, address, f_num, state):
        """Set Function Group 1
        
        This sets or clears a function in group 1.  The forward light
        is usually function number 0.

        If there is a function group 1 command in the packet list for the
        addressed decoder it is updated. Otherwise the command is added
        to the list.

        See NMRA S-9.2.1  Section 2.3.4
        
        args:
            address: the address of the decoder - may be short or long
            f_num:  function number to set or clear
            state:  1 for set, 0 for clear

        returns:
            True if validation is passed and the command is added
            to the list or modified. False if validation fails.   
        """
        # a bit of defensive programming
        if not (1 <= address <= CommandPacket.MAX_LONG_ADDR):
            return False
        if not (0 <= f_num  <= 4):
            return False
        if not state in (DCCCommand.ON,  DCCCommand.OFF):
            return False

        # function group 1 packet - single instruction byte
        try:
            self._get_cmd((FGrp1Command.TYPE, address)).update(f_num, state)
        except KeyError:
            self._add_cmd(FGrp1Command(address, f_num, state))

        return True
    
    def read_cv(self, address, cv_num):
        """Read CV (POM)
        
        This initiates reading a CV using Programming on Main in conjunction with RailCom.

        The command is validated and the read request scheduled for action. The addressed
        decoder must be active and the command will be rejected by the command generator class
        this is not true.

        args:
            address: decoder address
            cv_num: cv number as entered - users count from 1, DCC counts from 0!

        """
        if not (1 <= cv_num <= 1024):
            return False
        return self._pom_cmd(CV_Access(address, cv_num - 1))
    
    def write_cv(self, address, cv_num, new_val):
        """Write CV (POM)
        
        This initiates writing a CV using Programming on Main in conjunction with RailCom.

        The command is validated and the write request scheduled for action. The addressed
        decoder must be active and the command will be rejected by the command generator class
        this is not true.

        args:
            self:
            address:
            cv_num: cv number as entered - users count from 1, DCC counts from 0!
            new_val: the new value for the CV
        """
        if not (1 <= cv_num <= 1024):
            return False
        if not (0 <= new_val <= 255):
            return False
        return self._pom_cmd(CV_Access(address,
                                       cv_num - 1,
                                       operation = 'w',
                                       value = new_val))
        
    def _get_cmd(self, key):
        """Get a command from the packet list
        
        raises KeyError if not found
        """
        return self._packet_list[key]
    
    def _add_cmd(self, command):
        """Add Command to Packet List"""
        type = command.type
        addr = command.address
        self._packet_list[(type, addr)] = command
        self._active_address.add(addr)

    def _pom_cmd(self, command):
        """Process Program on Main command

        The response to a POM command may be delayed. The decoder does not
        have to put the POM response in the immediately following window and
        may respond following a subsequent command to that decoder.
        
        To ensure that there is a subsequent command the address is checked
        to see if in the active list. The command will be rejected if the
        address is not in the active list or there is a POM command already
        being processed.

        return:
            True if command accepted
            False if command rejected
        """
        if command.address not in self._active_address:
            return False
        if self._pom_packet is not None:
            # POM commands are temporary and only 1 is allowed
            return False
        self._pom_packet = command
        return True

    def _nxt_packet(self, _):
        """ Generate next packet.
        
        This runs in soft interrupt or timer callback context.
        
        This is called when the next packet in the
        list is to be serialised out on the DCC interface.
        If the list is empty or if the next packet is unavailable (e.g. being updated)
        the DCC Idle packet is serialised.

        The function is triggered via a soft ISR.  If RailCom is enabled, this is connected to the enable
        pin rising indicating the end of the cutout period assocated with the preceding command.

        **TODO** If RailCom not enabled this will be triggered by the PIO program itself when serialising the packet
        end bit. 
        
        This function instructs the next Command object in the list to send its command.
        """
        if self._dcc_gen_pio.pio_pwr() == DCCCmdTx.OFF:
            # power now off - don't transmit.
            self._dcc_gen_pio.pio_off() # deactivate pio sm now cycle complete
            return
        if self._packet_list: 
            if self._pom_packet is None:
                # POM packet if there takes precidence
                try:
                    # get the next packet in the list
                    next_pkt = self._packet_list[next(self._packet_iter)]
                except StopIteration:
                    # at end of list - renew iterator
                    self._packet_iter = iter(self._packet_list)
                    next_pkt = self._packet_list[next(self._packet_iter)]
            else:
                next_pkt = self._pom_packet

            if next_pkt.is_locked(): # packet being updated
                next_pkt = self._idle_packet # send idle packet instead
        else:
            # packet list empty
            next_pkt = self._idle_packet # send idle packet
        
        self._dcc_gen_pio.pio_send(next_pkt)

        if self._pom_packet is not None:
            # just sent a pom packet
            if self._pom_packet.all_sent():
                # check all sent
                # POM commands get deleted once sent
                self._pom_packet = None
        try:
            self._counts[next_pkt.type] += 1
        except KeyError:
            self._counts[next_pkt.type] = 1
        return

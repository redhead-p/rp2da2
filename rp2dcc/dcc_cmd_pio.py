"""DCC Command Serialisation PIO module
    :author: Paul Redhead

This module contains the class and functions for low level DCC Command Serialisation for use with RailCom detection.

An RP2040 Peripheral Input Output (PIO) block is used to generate the DCC signal. A 'booster'
is required to enable to track to be powered.  One of the many DC motor H-bridge chips (e.g. DRV8874)
should be suitable. The sleep pin puts the H-bridge into sleep mode when track power is not required.
The enable pin is used for the RailCom cutout, putting both sides of the bridge into low impedence mode
to ground and thereby creating the circuit required for the RailCom back channel.

A command comprises a preamble, one or more instruction/data bytes and an error detection (checksum) byte.
Each byte is preceeded by a single '0' bit.
The checksum is followed by a single '1' bit which may be the initial bit of
the next preamble. The preamble is at least 14 '1' bits. Note that in this implementation the pre-amble is
not interrupted by the cutout so the preamble length doesn't need to be lengthened but for compliance
RCN-217 the pre-amble is set to 18 bits.

The DCC signal is a series of '1' & '0' bits.  Each bit is encoded
into a complete DCC output cycle.  The half cycle length for a '1' is 58us, a '0' is 100us.
The DCC output pin is set high for the first half cycle of a bit and low for
second half cycle.
The PIO FIFO buffer is 32 bits wide - 1 word.  The RX FIFO is 
not used so is joined to the TX FIFO.  This gives a total FIFO of 8 words. Each word holds two DCC command
bytes plus framing bits. 

If the FIFO is empty, the PIO doesn't stall but continues outputing '0' bits until the FIFO is 
loaded with a new command.

RCN-210 &  RCN-211 partly apply as appropriate. 

See also NMRA Standards S 9.2 and S 9.2.1. S 9.2.1.1 is not supported.
"""
"""        Copyright (C) 2023, 2024, 2025 Paul Redhead

        This program is free software: you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the Free Software Foundation, 
        either version 3 of the License, or (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
        See the GNU General Public License for more details.
        You should have received a copy of the GNU General Public License along with this program.
        If not, see <http://www.gnu.org/licenses/>.
"""

# stop pylance reporting undefined variables for PIO code
# pyright: reportUndefinedVariable=false

from machine import Pin

from micropython import const

import rp2


# module constants - not for importing elsewhere
_PIO_FREQ = const(500_000)          # 500 kHz - 2 micro sec. tick period


class DCCCmdTx:
    """ DCC Output Transmit

    This singleton class manages the serialisation of DCC command packets to the track.

    The PIO has to be fed with words.  If the top bit (bit 31) is clear the word contains
    pre-amble ('1's) or two framing bit/command byte combinations.  18 bits are output.
    If bit 31 is set and bit 30 is clear the word contains a single framing bit/command byte.
    9 bits are output.
    If both bits 31 and 30 are set, the word contains the packet end bit, which will also trigger
    the RailCom cutout. 
    The Packet End Bit is encoded as a final word
    with bit 8 set.  Bit 7 must be set too if the cutout is to be generated.
    Normal command databytes are preceeded by a '0' start bit.

    Both short (7 bit) and long (14 bit) Multifuntion (mobile) decoder addresses are catered for
    but note that an address in the range 1 to 127 will be interpreted as a short address
    and an address in the range 128 - 10239 will be interpreted as a long address. I.e a mobile
    decoder with a long address in the range 0 - 127 is not addressable.

    A RailCom cutout is inserted following the transmission of a DCC command.

    Attributes:
        FWD:    Forward direction
        REV:    Reverse direction
        ON:     Power On
        OFF:    Power Off  
    """


    # class constants - may be imported by other modules

    FWD = const(1)
    REV = const(-1)

    ON = const(1)
    OFF = const(0)

    # class variables

    _this_dcc = None # the singleton DCC Command tx instance
    
    @classmethod
    def get_instance(cls):
        """ Get the DCC Command tx instance.

        This returns the singleton instance of the DCC Generator.

        Args:
            cls:

        Returns:
            The DCC generator instance
        """

        return cls._this_dcc
    
    @classmethod
    def get_state_machine(cls):
        """ Get the DCC generator state machine instance.

        This returns the single instance of the DCC generator PIO state machine.
        
        Args:
            cls:

        Returns:
            The DCC generator state machine
        """

        return cls._this_dcc._sm
    
    
    def __init__(self, sm_num, DCC_pn, sleep_pn, cu_pn):
        """ DCC serialisation  constructor
        
        This initialises the DCC serialisation singleton.  An attempt to create a 2nd
        instance will cause a runtime error.  The PIO state machine is allocated and initialised.
        
        Pins parameters are provided as Pin objects - not numbers!

        If RailCom cutouts are required the cutout generator must use a PIO state machine in the same PIO
        block.
        
        Args:
            sm_num: PIO state machine number to be used.
            DCC_pn: Pin allocated for DCC output.
            sleep_pn: Pin allocated to the booster for powering the track
            cu_pn:  Pin for cutout (DRV8874 enable) - set low by PIO
        """

        if not DCCCmdTx._this_dcc is None:
            raise RuntimeError ('Attempt to create 2nd DCC gen')
        DCCCmdTx._this_dcc = self
        
        # set up the PIO state machine for DCC serialisation
        self._sm = rp2.StateMachine(sm_num, self._dcc_tx, freq = _PIO_FREQ,
                                    out_base = cu_pn,
                                    set_base = DCC_pn)                    
        self._sleep_pin = sleep_pn
        
    @rp2.asm_pio(out_init = rp2.PIO.OUT_HIGH,
                set_init = rp2.PIO.OUT_HIGH,  
                out_shiftdir = rp2.PIO.SHIFT_LEFT, 
                fifo_join  = rp2.PIO.JOIN_TX)
    def _dcc_tx():
        """PIO Serialise DCC Command
        
        This is the PIO DCC command transmitter. A GPIO pin is used for the DCC output. This pin is
        set or cleared with the 'set(pins, ...)' command using the set_base pin as allocated for
        the state machine.

        A second GPIO pin, connected to the DRV8874 enable pin controls the RailCom cutout. The
        pin is normally high, and set low during for the cutout, setting both sides of the
        H-bridge to low impedance and thereby connecting the two track rails. This pin is
        allocated to the state machine as out_base and its state changed using the  'mov(pins, ...)
        command. Using separate bases allows the state of the two pins
        to be managed independently.

        OSR is set to shift left so the Most Significant bits are shifted out first.

        The RX FIFO is joined to the TX FIFO so doubling the TX FIFO length.

        As this is output only we can use the Input Shift Register (ISR/isr) as an additional store.

        **TODO** There needs to be an option to allow for generation of DCC without the RailCom cutout.
        """
    
        wrap_target()
        # do nominally high side of the cycle first - 2 ticks so far (except 1st time!)
        # dcc pin preset high in decorator

        #  set x to default value for OSR to be used if FIFO empty
        #  0 for '0's
        #  9 ticks from here to 'nxt_bit' for both paths
        set(x, 0)                   [0]
        # pull word from FIFO
        # 32 bits are pulled - 2 by 9 bit outputs
        # if FIFO is empty register x (0) is copied to OSR
        # so we send 18 '0's (taking 3.6ms)
        pull(noblock)               [0]
        out(x,1)                    [0]    # get first (MS) bit
        jmp(not_x, "dbytes")        [0]    # if 0 it's  normal data bytes in 18 bits or preamb

        # 6 ticks so far + 6 -> 12 cumulative
        # 9 bits in this word - either packet end (+ cutout) or single byte - right aligned

        # put the packet end indicator bit in y - it's cleared on the next data byte
        out(y,1)                    [0]     # pick up packet end control bit
        jmp(not_y, "dbyte")         [0]     # data - not packet end / cutout
        # packet end bit
        out(null, 28)               [0]     # discard unused bits levaing PE bit + 2 bits filler
        # y set for cut out required but this will be on next bit
        jmp("get_nxt")              [4]     #


        label ("nxt_bit")
        # 12 ticks so far
        # do we need to start cutout?
        mov(x, isr)                 [0]    # get cu out bit - will have been set at end of preceeding bit
        jmp(not_x, "get_nxt")       [0]    # jump if not to insert cutout
        # start cut out - 14 ticks / 28µs after trailing edge of packet end bit.
        # bit serialisation is paused during cutout but we preserve the timeing as if
        # it had continued during the cut out so at the end of the cut out we will have
        # the low side of a '1' to complete.
        mov(pins, invert(x))        [0]    # start cutout mov -> out base
        set(pins, 0)                [0]    # set DCC low for end of cutout - no effect till end of cutout 
        set(x,19)                   [0]    # 20 times round loop - 11 ticks per loop > 220

        label("pause")
        jmp(x_dec,"pause")          [10]   # total cutout duration 220 + 3 ticks -> 446 µs
        mov(pins, isr)              [12]   # re-enstate enable to end cutout - 26 ticks low side '1' to go
        out(x,1)                    [0]    # we are still doing a '1' bit - shift it from OSR
        jmp("low_end")              [0]

        # single databyte or preamb
        label("dbyte")
        out(null, 21)               [0]     # leaving 9 bits
        jmp("get_nxt")              [4]


        label("dbytes")
        # 6 ticks so far
        # cannot be packet end or cutout but could 18 bit preamble
        out(null, 13)               [7]     # discard unused bits leaving 18
    

    
        label("get_nxt")
        # 14 ticks all paths - 14 via nxt_bit is limiting 
        out(x,1)                    [0]    # get next output bit

        # 15 ticks so far for all paths 
        # 18  ticks high high for short (1) and long (0) - cummulative 28
        jmp(not_x, "long_high")     [12]    # if 0 it's long
        
        # 1 ticks high for short (1) only - cummulative 29 (full short 1st half cycle)
        jmp("short_low")            [0]     # it's short - low half cycle next
        
        label("long_high")
        # 22 ticks high for long (0) only - cummulative 50 (full long 1st half cycle)
        nop()                       [21]    # long half cycle is 21 ticks longer

        # 21 ticks low for long (0) only - cummulative low 21 (2nd half cycle) 
        set(pins, 0)                [20]     # for long low start

        label("short_low")
        # cummulative 21 ticks (0) low and 0 for '1' bit
        # 29 ticks low for short (1) and long (0) - cummulative short 29, long 50 (full cycles)
        set(pins, 0)                [26]    # common part - both 1 & 0
 
        mov(isr, y)                  [0]     # copy cu flag to isr - it will be picked up in the next bit
        set(y, 0)                    [0] #and clear it


        label("low_end")
        # 50 ticks long - 29 short - both complete
        set(pins, 1)                [0]     # set back to high - restart tick count here
        jmp(not_osre, "not_done")   [0]
        wrap()                              # pull from FIFO & start next single bit/ byte group 



        label("not_done")
        # 2 ticks so far 
        # 10 ticks high for short (1) and long (0) 
        # this isn't the last bit but it might be the packet end bit if cutout is enabled

        jmp("nxt_bit")              [9]     # done this bit - do next bit            

        # 31 PIO instructions - 1 spare
    

    def pio_pwr(self, p = None):
        """DCC Power On/Off
        
        On power on we
            - de-assert the booster sleep pin (1 for False)
            - start the DCC generator state machine

        On power off we assert the booster sleep pin (0 for True)

        The state machine will be stopped when the current command cycle is complete.

        args:
            p: 1 for power on, 0 for power off, None for get power status

        returns:
            power status as held by the power pin
        """
        if (p is None):
            return self._sleep_pin()
        if p == DCCCmdTx.ON:
            self._sleep_pin(1)
            self._sm.active(True)
        else:
            self._sleep_pin(0)
        return self._sleep_pin()
    
    def pio_off(self):
        """Stop PIO State Machine
        
        """
        self._sm.active(False)



"""DCC RailCom DCC Command Response
    :author: Paul Redhead

This module contains the functions and classes for DCC RailCom DCC command mobile responses on Channel 2.

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

import time
from collections import deque
from micropython import const

from hw_conf import HwConfGbl
from dcc_rc_pio import RailComRead
from dcc_cmd_util import CommandPacket, CV_Access
from device import Device


_DG2_LEN = {0:1, 1:1, 2:1, 3:5, 4:5, 7:2, 8:5, 9:5, 10:5, 11:5, 12:5, 13:5, 14:1}
""" Channel 2 Datagram Length

This is for mobile decoders - see RCN-217  Table 6. The table for accessory (static) decoders
differs, but no plans to support them yet.

Indexed by datagram id, contains the additional number of 6 bit groups to be concatenated.
"""


class RComCmdRsp(RailComRead):
    """Channel 2 (Command Response) Decode
    
    This runs on the command station. As there is only one DCC generator there can only be
    one of these too.

    Datagram identifiers for channel 2 are defined in RCN-217 3.1 Table 6.

    Attributes:
        DG_POM: POM response (CV value) datagram identifier.
        DG_TS1: track search 1
        DG_TS2: track search 2
        DG_TS14: track search 14
        DG_EXT: location information
        DG_CDI: current driving info - not specified yet
        DG_DYN: dynamic info (DG ID 7) datagram identifier.
        DG_XPOM8: extended POM response - 1st CV
        DG_XPOM9: extended POM response - 2nd CV
        DG_XPOM10: extended POM response - 3rd CV
        DG_XPOM11: extended POM response - 4th CV
        DG_CV_AUTO: Background CV transmission
        DYN_REAL_SPEED: real speed part 1 datagram identifier.
        DYN_REAL_SPEED1: real speed part 2 datagram identifier.
        DYN_RECEP_STATS: reception stats datagram identifier.
        DYN_TRACK_VOLT: track voltage
        DYN_DIRECTION: direction status byte
        DYN_TEMP: decoder temperature
        ERR_CODE: list of error codes
    """
    # class constants
    # datagrams and contents
    DG_POM = const(0)       # POM response (CV value)
    DG_TS1 = const(1)       # track search 1
    DG_TS2 = const(2)       # track search 2
    DG_TS14 = const(14)     # track search 14
    DG_EXT = const(3)       # location information
    DG_CDI = const(4)       # current driving info - not specified yet
    DG_DYN = const(7)       # datagram with dynamic info (DG ID 7)
    DG_XPOM8 = const(8)     # extended POM response - 1st CV
    DG_XPOM9 = const(9)     # extended POM response - 2nd CV
    DG_XPOM10 = const(10)     # extended POM response - 3rd CV
    DG_XPOM11 = const(11)     # extended POM response - 4th CV
    DG_CV_AUTO = const(12)  # Background CV

    DYN_REAL_SPEED  = const(0) # real speed part 1 - this is the index used for speed
    DYN_REAL_SPEED1 = const(1) # real speed part 2 - not used.
    DYN_RECEP_STATS = const(7) # reception stats
    DYN_TEMP = const(26)       # temperature
    DYN_DIRECTION   = const(27)# direction status byte
    DYN_TRACK_VOLT  = const(46)# track voltage
    
    # error codes as detected by low level code
    ERR_CODE = (RailComRead.ERR_WH, RailComRead.ERR_WL, RailComRead.ERR_OE, RailComRead.ERR_CB)

    _rc_ch2 = None

    @classmethod
    def get_instance(cls):
        """ Get the RailCom ch2 detector instance.

        This returns the singleton instance.
        It is instantiated on the first call.

        Returns:
            The RailCom ch2 detector instance
        """
        if cls._rc_ch2 is None:
            cls._rc_ch2 = RComCmdRsp()
        return cls._rc_ch2

    def __init__(self):
        """DCC Command object constructor
        

        The enable pin is that used to enable the DRV8874. It's set by the DCC generator PIO.
        It's monitored here by the PIO program as
        it's low going edge marks the start of the cutout.

        The RailCom reader for channel 2 is instantiated and the base class is initiated.

        Note:
            The RailCom reader will use two sequentially numbered state machines -
            the first is read from the hardware configuration.

            The RailCom reader will use two sequentially numbered GPIO pins for receiving -
            the first is read from the hardware configuration.
        """
        assert RComCmdRsp._rc_ch2 is None, 'Attempt to create 2nd RC ch2 detector'
        RComCmdRsp._rc_ch2 = self
        self._dyn_info = {} # other dynamic info
        self._dyn_chng = deque([],32) # addresses with dynamic info changes
        self._pom_acc = {}   # outstanding cv accesss requests by command type/address

        self._errors = {} # error counts
        self._dgs = set() # Datagrams seen

        hwconf = HwConfGbl.get_instance()
        rc_sm_num = hwconf.RC2_STATE_MC
        rx_pn, enable_pn = hwconf.rc2_pins
        super().__init__('cmd', rc_sm_num, rx_pn, cu_pin = enable_pn)

    def get_error_counts(self):
        """ Get Error Counts
        
        Diagnostic method to retrieve the error counts for detected errors.
        
        returns:
            a dictionary of counts by error code.
        """
        return self._errors
    
    def get_dg_list(self):
        """ Get Datagram list
        
        Diagnostic method to retrieve the list of datagram types that have been  decoded.
        
        returns:
            the set of datagram ids
        """
        return self._dgs
    
    def get_dyn_chng(self):
        """ get changes to dyn info

        returns:
            dyn info for first address in queue
        """
        try:
            addr = self._dyn_chng.popleft()
        except IndexError:
            # queue empty
            return 0,[]
        return addr, [(si, self._dyn_info[(a, si)]) for (a, si) in self._dyn_info.keys()
                  if a == addr]

    def reset_stats(self):
        """ Reset diagnostic information
        
        Clears the error counts and set of datagram ids.
        """
        self._errors = {}
        self._dgs = set()

    def _log_error(self,error_code):
        try:
            self._errors[error_code] += 1
        except KeyError:
            self._errors[error_code] = 1

    def _rail_com_msg(self, buffer):
        """Process RailCom Channel 2 response
        
        This is called on termination of the RailCom Channel 2 message receipt window,
        when a response is detected. The addressed decoder returns a channel 2
        message. Other mobile decoders remain silent.

        It overrides the method in the base class.

        Blank reads should have been intercepted in the hard ISR. They are not checked for 
        here but should not be problematic.

        args:
            buffer:   raw data
        """
        cmd = CommandPacket.get_last_command()
        if cmd is None:
            # no point in continuing if we don't know what command was issued
            self._log_error(RailComRead.ERR_RESP)   # no command - possible software sync error
            return
        address = cmd.get_address()
        if address == 255:
            # broadcast address - reserved for RailCom Plus response 
            # not used for RailCom
            return
        if cmd.get_type() == CV_Access.TYPE:
            # maybe already there (second write) - quietly update or add
            # get the request cv number and command timeout and save
            # the decoder has half a second to respond RCN217 5.1
            self._pom_acc[(address)] = (cmd.get_cv(), time.ticks_add(time.ticks_ms(), 500))
        else:
            # other command
            # check for outstanding POM command timeout
            try:
                cv, timeout = self._pom_acc[(address)] # get timeout
                if time.ticks_diff(time.ticks_ms(), timeout) > 0:
                    # timeout expired
                    del(self._pom_acc[(address)]) # no longer needed
                    self.report_event(Device.POM_TO, (address, cv + 1))
            except KeyError:
                # no outstanding POM command
                pass
        self._act_on_datagram(self._parse_cg2_msg(buffer), address)

    def _parse_cg2_msg(self, buff):
        """ Parse Channel 2 Message
        
        Inspect the message and extract datagrams which are saved in list and returned.
        The datagrams are tuples of (datagram id, payload).
        Bytes are either protocol control bytes, error bytes or data bytes. The least significant 6 bits of a
        data byte contrinbute to the payload of a datagram and the most significant 2 bits are ignored. The payload
        content of each byte is concatenated to form the datagram. The datagram id is
        the first 4 bits of the datagram. The datagram id is used to determine the length of the datagram.
        """ 
        buff_iter = iter(buff)
        dg_id = None
        pb_set = set() # set of protocol bytes
        datagram = list()

        try:
            # StopIteration will end the loop
            while True:
                b = RailComRead.hw4_2_6b(next(buff_iter))
                if b > 0x3f:
                    if b in RailComRead.PROT_BYTE:
                        # encoded protocol bytes
                        # these only get reported once so save in a set
                        # as ACK may be used as filler
                        if b not in pb_set:
                            # first time seen - ignore repeats
                            datagram.append((RailComRead.DG_RESP, b))
                            self._dgs.add(RailComRead.DG_RESP)
                            pb_set.add(b)
                    elif b in RComCmdRsp.ERR_CODE:
                        # Recognised Error code
                        # no point in going any further - as structure of
                        # remaining message indeterminate
                        if b != RailComRead.ERR_OE:
                            self._log_error(b)
                        return datagram
                else:
                    # separate the datagram id and first 2 bits of payload
                    dg_id = (b & 0xFC)  >> 2
                    dg_payload = b & 0x03
                    try:
                        error = False
                        for _ in range(_DG2_LEN[dg_id]):
                            b = RailComRead.hw4_2_6b(next(buff_iter))
                            if b > 0x3f:
                                if b in RComCmdRsp.ERR_CODE:
                                    # Recognised Error code
                                    # no point in going any further - as structure of
                                    # remaining message indeterminate
                                    self._log_error(b)
                                    error = True            
                                else:
                                    # datagram can't include protocol control byte
                                    self._log_error(RailComRead.ERR_CB)
                                    error = True # so this and any more are ignored
                            elif error:
                                # error already seen - skip 
                                pass
                            else:
                                dg_payload = (dg_payload << 6) + b # append sextet to payload
                        # payload complete
                        if not error:
                            self._dgs.add(dg_id)
                            datagram.append((dg_id,dg_payload))

                    except KeyError: # not valid datagram (not in list)
                        # no point in going any further - as structure of
                        # remaining message indeterminate
                        self._log_error(RailComRead.ERR_ID)
                        return datagram

                    dg_id = None  # set back to None to mark datagram complete

        except StopIteration:
            if dg_id is not None:
                # datagram not complete - ignore it - duff format
                # other earlier datagrams in same message will be processed
                self._log_error(RailComRead.ERR_FE)
        return datagram

    def _act_on_datagram(self, datagram, addr):
        for id, payload in datagram:
            if id == RComCmdRsp.DG_DYN:
                # dynamic information RCN217 5.5
                dyn_si = payload & 0x3F # extract subindex
                value = payload >> 6
                if dyn_si <= 1: # speed subindex 0 or 1
                    # sub index 0 : 0 - 255 kph, 1 : > 256 
                    # store speed under sub-index 0
                    value = value + (dyn_si << 8)
                    dyn_si = 0
                try:
                    old_val = self._dyn_info[(addr, dyn_si)]
                except KeyError:
                    old_val = None
                if old_val is None or old_val != value:
                    #update value
                    self._dyn_info[(addr, dyn_si)] = value
                    # and add address to list of changes
                    if addr not in self._dyn_chng:
                        try:
                            self._dyn_chng.append(addr)
                        except IndexError:
                            self.report_event(Device.CH2_Q_FULL,None)

            elif id == RComCmdRsp.DG_POM:
                # POM cv response RCN219 5.1
                # payload is cv value from last POM command
                # check that there was one for this address
                try:
                    cv, _= self._pom_acc[(addr)]
                    del(self._pom_acc[(addr)]) # no longer needed
                    self.report_event(Device.POM_CV, (addr, cv + 1, payload))
                except KeyError:
                    pass
            elif id == RailComRead.DG_RESP and payload == RailComRead.NAK:
                try:
                    cv, _= self._pom_acc[(addr)]
                    del(self._pom_acc[(addr)]) # no longer needed
                    self.report_event(Device.POM_NAK, (addr, cv + 1))
                except KeyError:
                    pass         

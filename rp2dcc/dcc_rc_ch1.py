"""DCC RailCom Block Detection
    :author: Paul Redhead

This module contains the functions and classes for DCC RailCom block detection on Channel 1.

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
import asyncio

from machine import  Timer
from micropython import const

from dcc_rc_pio import RailComRead
from device import Device

_MAX_NO_READ = const(10)    # maximum number of missed reads/no load
_TIMER_PERIOD = const(50)   # time in ms between checks for current load on block 
_CONSIST_ADDR_MASK = const(0x7F)      # DCC consist address mask
_MAX_LONG_ADDR = const(0x27FF)      # DCC long address upper limit (inclusive)


class RComBlkDet(RailComRead):
    """Channel 1 (block) Detector
    
    This runs on an accessory controller.
    
    The PIO code monitors
    the load current to detect the cutout.

    In addition to interpreting channel 1 messages, we use the rx_pin to monitor the block for occupancy, detecting
    non RailCom decoders and other loads. E.g coaches with lighting etc. This detection is typically not as sensitive
    as other current based detectors as it uses same thresholds as required for RailCom message detection.

    It's taken that a decoder may only be in one place at a time, but the implications of this are dealt with
    elsewhere.

    Datagram identifiers for channel 1 are defined in RCN-217 3.1 Table 5.

    This inherits from the RailComRead Class.

    Block status may be:
        - empty
        - occupied, but no RailCom Channel 1 info available
        - occupied and RailCom Channel 1 info available

    Attributes:

        DEVICE_TYPE: Device type for reporting events.
        _MAX_LONG_ADDR: DCC Maximum long address
        _SHORT_ADDR_MASK: DCC short address mask.
    """
    

   
    def __init__(self, blk_name, rc_sm_num, rx_pin):
        """Construct the RailCom block detector
        
        This constructs the RailCom block detector. This reads channel 1. It instatiates a RailCom reader using
        the supplied state machine and receiver pin. 
        This runs on a remote accessory controller and the cutout timing is recovered from the DCC signal.
        The base RailCom class is initiated with the block name.
        block type.

        Note:
            The RailCom reader will use two sequentially numbered state machines - the first is supplied.

            The RailCom reader will use two sequentially numbered GPIO pins for receiving - the first is supplied.

        args:
            blk_name: the name of the block
            rc_sm_num:  the first state machine number.
            rx_pin: the first receiver pin.
        """

        self._id_val = {} # channel 1 payload values for ids 1 & 2
        self._load_timer = Timer()
        self._rx_pin = rx_pin
        self._no_resp_count = _MAX_NO_READ
        self.reset_stats()

        """block state may be unknown, empty, occupied (no channel 1 data),
        occupied with channel 1 data"""
        self._blk_state = (Device.UNKNOWN, None) # block state is status and RailCom info if available.
        self._load_timer.init(mode = Timer.PERIODIC, period = _TIMER_PERIOD, callback = self._load_check)

        self._ready_flag = asyncio.ThreadSafeFlag() # used to signal new state available to comms agent

        super().__init__(blk_name,
                        rc_sm_num,
                        rx_pin)

    async def wait_for_flag(self):
        """ Wait for the new state available flag

        This waits for the asynchio thread safe flag to be set.
        """
        await self._ready_flag.wait()
        return
    
    def report_event(self, event, data):
        """ Report Event
        
        This overrides the Device.report_event method.
        It sets the thread safe flag to indicate block status change.
        
        args:
            event:  updated Block status code.
            data:   a tuple containing address type, address & orientation  
        """
        self._ready_flag.set()
        super().report_event(event, data)

    def get_error_counts(self):
        """ Get Error Counts
        
        Diagnostic method to retrieve the error counts for detected errors.
        
        returns:
            a dictionary of counts by error code.
        """
        return self._errors
    
    def get_cb_count(self):
        """ Get Read Count
        
        returns:
            the number of times the detector read function has been called.
        """
        return self._cb_count
    
    def reset_stats(self):
        """ Reset diagnostic informations
        
        Clears the error counts and set of datagram ids.
        """
        self._errors = {}
        self._cb_count = 0  # number of times called back

    def get_block_state(self):
        """ Get the current block state
        
        This returns the current block state. The block state is a tuple of
        the block status and any RailCom information available.
        The block status may be:
        - Device.UNKNOWN: the block state is unknown
        - Device.EMPTY: the block is empty
        - Device.BLK_OCC: the block is occupied, but no RailCom Channel 1 information is available
        - Device.BLK_CH1: the block is occupied and RailCom Channel 1 information is available
        """
        return self._blk_state

    def _log_error(self,error_code):
        try:
            self._errors[error_code] += 1
        except KeyError:
            self._errors[error_code] = 1

    def _load_check(self, _):
        """ Load check timer expired callback

        Check to see if there's a load on the block. I.e. the current is greater than
        the '0' RailCom value.
        """

        if self._rx_pin() == 1:
            # no load
            if self._no_resp_count < 0:
                if self._blk_state[0] != Device.BLK_EMPTY: 
                # consecutive missed response limit reached
                # but it's not been reported
                    self._id_val = {} # clear any previous datagrams
                    self._last_report = None
                    self._blk_state = (Device.BLK_EMPTY, None)
                    self.report_event(*self._blk_state)
            else:
                self._no_resp_count -= 1
        else:
            # false positive unlikely so report change immediately if was empty
            # but allow limit misreads if last report was CH1 data
            if self._blk_state[0] not in (Device.BLK_OCC, Device.BLK_CH1):
                # either empty or start of day
                self._no_resp_count = _MAX_NO_READ
                self._blk_state = (Device.BLK_OCC, None)
                self.report_event(*self._blk_state)
            elif self._blk_state[0] == Device.BLK_CH1:
                if self._no_resp_count < 0:
                    # consecutive limit reached
                    self._id_val = {}
                    self._last_report = None
                    self._blk_state = (Device.BLK_OCC, None)
                    self.report_event(*self._blk_state)
                else:
                    self._no_resp_count -= 1
            else:
                self._no_resp_count = _MAX_NO_READ  # reset the count
        
    def _rail_com_msg(self,  buffer, orientation):
        """ This is called on termination of the RailCom Channel 1 message receipt window,
        whether a message has been received or not.
        Any decoder on the associated block returns a channel 1 message.

        Calls RailComRead.hw4_2_6b() to translate from raw byte to internal value.

        args:
            self:
            buffer:   raw data
            orientation: orientation of DCC decoder wrt DCC signal
        """
        self._cb_count += 1 

        try:
            rx1 = RailComRead.hw4_2_6b(buffer[0])
            if rx1 == RailComRead.ERR_OE:
            # first character has overrun - most likely switching noise after end of window
            # or false trigger - not logged or parsed
                return
        except IndexError:
            return # nothing there - not logged

        # other errors indicate datagram corruption - possibly due to >1
        # decoder in block or crossing block boundary
        try:
            rx2 = RailComRead.hw4_2_6b(buffer[1])
        except IndexError:
            # too short (too long shouldn't be possible)
            self._log_error(RailComRead.ERR_FE) # log as datagram format error
            self._id_val = {} # clear any previous datagrams
            return

        
        for b in rx1, rx2:
            if b > 0x3f:
                # it's some kind of error
                self._id_val = {} # clear any previous datagrams
                if b in RailComRead.PROT_BYTE:
                    # control character - not allowed in channel 1
                    self._log_error(RailComRead.ERR_CB)
                else:
                    # it's an error code 
                     self._log_error(b)
                return # stop parsing
        
        # save the payload value against the id
        dg_id = rx1 >> 2
        if not (0 < dg_id <= 3):
            # invalid datagram id 
            self._log_error(RailComRead.ERR_ID)
            return
        # both values need to be present to get this far
        # there's a valid response so reset the 'no response' count
        self._no_resp_count =  _MAX_NO_READ
        self._id_val[dg_id] =  ((rx1 & 0x03) << 6) | rx2 # assemble payload
  
        # try and build decoder address
        try:
            if self._id_val[1] == 0:
                # short address
                address = self._id_val[2]
                if not (0 < address < 128):
                    # invalid short address - must be 1 to 127
                    self._log_error(RailComRead.ERR_PL)
                    self._id_val = {} # clear both - either could be wrong
                    return
                address_type = 's'
            elif self._id_val[1] == 0x60:
                # consist address
                address_type = 'c'
                address = self._id_val[2] & _CONSIST_ADDR_MASK
            elif (self._id_val[1] & 0xc0) == 0x80:
                # long address
                address_type = 'l'
                address = (self._id_val[1] & 0x3f) << 8 + self._id_val[2]
                if address > _MAX_LONG_ADDR:
                    self._log_error(RailComRead.ERR_PL)
                    self._id_val = {} # clear both - either could be wrong
                    return
            else:
                # ID1 content invalid - ignore
                self._log_error(RailComRead.ERR_PL)
                return
        except KeyError:
            # missing id 1 or id 2
            # insufficient info - there may be enough next time!
            return
        
        # if the occupancy report has changed since the last time
        # report the event and update saved info for next time.
        report_data = (address_type, address, orientation)
        if report_data != self._blk_state[1]: # occupancy info changed?
            self._blk_state = (Device.BLK_CH1, report_data)
            self.report_event(*self._blk_state)

"""DCC RailCom Block Detection
    :author: Paul Redhead

This module contains the functions and classes for DCC RailCom block detection on Channel 1.

"""
"""        Copyright (C) 2023, 2024, 2025,2026 Paul Redhead

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

from dcc_rc_pio import RailComRead
from device import Device
from hw_conf import HwConf


_CONSIST_ADDR_MASK = const(0x7F)      # DCC consist address mask
_MAX_LONG_ADDR = const(0x27FF)      # DCC long address upper limit (inclusive)
_RESP_TO = const(500)       # channel 1 response time out (ms)


class RComBlkDet(RailComRead):
    """Channel 1 (block) Detector
    
    This runs on a local block detector MCU.
    
    The PIO code monitors the load current to detect the cutout.

    Although in addition to interpreting channel 1 messages, we could use
    the rx_pin to monitor the block for occupancy, detecting
    non RailCom decoders and other loads. This detection would not be as
    sensitive as other current based detectors as it uses same thresholds
    as required for RailCom message detection.

    It's taken that a decoder may only be in one place at a time, but the
    implications of this are dealt with elsewhere.

    Datagram identifiers for channel 1 are defined in RCN-217 3.1 Table 5.

    This inherits from the RailComRead Class.

    Block status may be:
        - unknown (start of day)
        - no RailCom Channel 1 info available
        - RailCom Channel 1 info available
    """
    
    def __init__(self, blk_name, i):
        """Construct the RailCom block detector
        
        This constructs the RailCom block detector. This reads channel 1. It instatiates a RailCom reader using
        the supplied state machine and receiver pin. 
        This runs on a remote accessory controller and the cutout timing is recovered from the DCC signal.
        The base RailCom class is initiated with the block name.

        Note:
            The RailCom reader will use two sequentially numbered state machines - the first is supplied.

            The RailCom reader will use two sequentially numbered GPIO pins for receiving - the first is supplied.

        args:
            blk_name: the name of the block
            i: block index number (0 - 3)
        """
        hw_conf = HwConf.get_instance()
        rx_pin, rc_sm_num = hw_conf.get_lcl_det(i)

        self._id_val = {} # channel 1 payload values for ids 1 & 2
        self._rx_pin = Pin(rx_pin, Pin.IN)
        _ = Pin(rx_pin + 1, Pin.IN) # initialise orientation pin too
        self._dcc_pin = hw_conf.dcc_sense
        self.reset_stats()

        self._index = i

        """block state may have channel 1 data if ch1 responses received or None"""
        self._blk_state = None
     
        self._ready_flag = asyncio.ThreadSafeFlag() # used to signal new state available to comms agent
        self._ch1_dg_rx = asyncio.ThreadSafeFlag() # valid ch1 response resets no response timeout

        super().__init__(blk_name,
                        rc_sm_num,
                        self._rx_pin,
                        dcc_pin = self._dcc_pin)
        
        asyncio.create_task(self._check_resp())

    @property
    def index(self):
        """Block Index Number
        
        The block index number is derived from the blocks position in the configuration list. It's used
        to identify the Indicator led."""
        return self._index

    async def wait_for_flag(self):
        """ Wait for the new state available flag

        This waits for the asynchio thread safe flag to be set. This may be used by another thread
        to wait on a state change.
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
        """ Reset diagnostic information
        
        Clears the error counts and set of datagram ids.
        """
        self._errors = {}
        self._cb_count = 0  # number of times called back
    @property
    def block_state(self):
        """ Current block state
        
        This returns the current block state. The block state is a tuple containing
        the RailCom information available. If no RailCom information is available block
        is None.
     
        """
        return self._blk_state

    def _log_error(self,error_code):
        try:
            self._errors[error_code] += 1
        except KeyError:
            self._errors[error_code] = 1
        
    def _rail_com_msg(self,  _):
        """ This is called on termination of the RailCom Channel 1 message receipt window,
        when a channel 1 reponse has been detected (i.e. length > 0)
        Any decoder on the associated block returns a channel 1 message.

        Calls RailComRead.hw4_2_6b() to translate from raw byte to internal value.

        The method overrides that in the base class.

        Orientation of decoder wrt the DCC signal is saved as 1 or -1 e.g. s * 2 - 1

        Buffer contains 1 or 2 bytes. Zero length reads don't get this far.
        Longer reads are already truncated.

        Overrun errors on 1st byte are quietly ignored. Overrun error on 2nd byte is
        logged.

        If the buffer only 1 byte or one of the bytes is ACK or NAK or reserved
        in RCN-217 Table2, this is an error and is logged.

        The datagram ID must be 1, 2 or 3.  Type 3 datagrams are ignored. Other
        datagram IDs are logged as errors.

        As a protection against undetected errors, to be acted on a type 1 or 2 datagram
        must have the same payload as the preceding datagram of that type.

        args:
            _:   this paramater is only used for channel 2
        """
        self._cb_count += 1 
        rx1 = RailComRead.hw4_2_6b(self._rx_buff[0])
        if rx1 == RailComRead.ERR_OE:
            # first character has overrun - most likely switching noise after end of window
            # or false trigger - not logged or parsed
            return
        # other errors indicate datagram corruption - possibly due to
        # >1 decoder in block or crossing block boundary
        orientation = ((self._rx_buff[0] & 0x100) >> 7) - 1
        rx2 = RailComRead.hw4_2_6b(self._rx_buff[1])
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
        # there's a valid response so reset the monitor timer
        self._ch1_dg_rx.set()
        payload =  ((rx1 & 0x03) << 6) | rx2
        try:
            # confirm payload against previous entry
            if self._id_val[dg_id] != payload:
                self._id_val[dg_id] = payload #update if changed
                return # but nothing more this time
        except KeyError:
            # no previous entry
            self._id_val[dg_id] = payload
            return # await confirmation        
                 
        # try and build decoder address
        try:
            if not self._id_val[1]:
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
        if report_data != self._blk_state: # occupancy info changed?
            self._blk_state =  report_data
            self.report_event(Device.BLK_CH1, self._blk_state)

    async def _check_resp(self):
        """ Coroutine to monitor Ch1 responses

        This runs a time out timer. The timer is restarted if a Ch1 response is detected.
        If the timer expires the block is treated as being vacant as far as RailCom is concerned.
        Occupancy info is cleared.

        The coroutine task runs forever.        
        """
        while True:
            try:
                await asyncio.wait_for_ms(self._ch1_dg_rx.wait(), _RESP_TO)
            except asyncio.TimeoutError:
                # nothing happened.
                if self._blk_state is not None:
                    self._blk_state = None
                    self.report_event(Device.BLK_CH1, None)
                continue
            # event flag set - restart timeout
            self._ch1_dg_rx.clear()

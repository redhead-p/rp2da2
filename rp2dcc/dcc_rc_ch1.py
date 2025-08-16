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

from machine import  Pin, Timer
from micropython import const

from dcc_rc_pio import RailComRead
from device import Device

_MAX_NO_READ = const(10)    # maximum number of missed reads/no load
_TIMER_PERIOD = const(50)   # time in ms between checks for current load on block 
_FIRST_TIMER_PERIOD = const(1000)   # first check is delayed to let things settle


class RComBlkDet(Device):
    """Channel 1 (block) Detector
    
    This can run on the command station or an accessory controller.
    
    The enable pin is supplied if on the command station to mark the cutout. On accessory the PIO code monitors
    the load current to detect the cutout.

    In addition to interpreting channel 1 messages, we use the rx_pin to monitor the block for occupancy, detecting
    non RailCom decoders and other loads. E.g coaches with lighting etc. This detection is typically not as sensitive
    as other current based detectors as it uses same thresholds as required for RailCom message detection.

    It's taken that a decoder may only be in one place at a time, but the implications of this are dealt with
    elsewhere.

    Datagram identifiers for channel 1 are defined in RCN-217 3.1 Table 5.

    This inherits from the Device Class.

    Block status may be:
        - empty
        - occupied, but no RailCom Channel 1 info available
        - occupied and RailCom Channel 1 info available

    Attributes:

        DEVICE_TYPE: Device type for reporting events.

    """
    
    # class constants
    
    DEVICE_TYPE = const('b')
   

    def __init__(self, blk_name, rc_sm_num, rx_pin, enable_pin = None):
        """Construct the RailCom block detector
        
        This constructs the RailCom block detector. This reads channel 1. It instatiates a RailCom reader using
        the supplied state machine and receiver pin.  If the enable pin is not supplied, it's assumed that 
        this is running on a remote accessory controller and the cutout timing is to be recovered from the DCC signal.
        If the enable pin is supplied, then we are running on the command station and the cutout is defined by the
        enable pin state, which is read-only in this context. The base Device class is initiated with the block name
        block type.

        Note:
            The RailCom reader will use two sequentially numbered state machines - the first is supplied.

            The RailCom reader will use two sequentially numbered GPIO pins for receiving - the first is supplied.

        args:
            self:
            blk_name: the name of the block
            rc_sm_num:  the first state machine number.
            rx_pin: the first receiver pin.
            enable_pin: the pin as used by the DCC generator to assert the RailCom cutout (optional).

        """
        self._rc = RailComRead(rc_sm_num, rx_pin,  self._rail_com_ch1_msg, channel = 1, cu_pin=enable_pin)
        self._id_val = {} # channel 1 payload values for ids 1 & 2
        self._rx_pin = rx_pin
        self._enable_pin = enable_pin
        self._no_resp_count = _MAX_NO_READ

        # block state may be unknown, empty, occupied (no channel 1 data), occupied with channel 1 data
        self._blk_state = (Device.UNKNOWN, None) # block state is status and RailCom info if available.
        self._load_timer = Timer(mode = Timer.ONE_SHOT, period = _FIRST_TIMER_PERIOD, callback = self._load_check)
        self._errors = {} # Error counts by type
        self._dgs = set() # Datagrams seen
        super().__init__(blk_name, RComBlkDet.DEVICE_TYPE)


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
    
    def reset_stats(self):
        """ Reset diagnostic informations
        
        Clears the error counts and set of datagram ids.
        """
        
        self._errors = {}
        self._dgs = set()

    def get_block_state(self):
        """ Get the current block state
        
        This returns the current block state. The block state is a tuple of the block status and any RailCom
        information available. The block status may be:
            - Device.UNKNOWN: the block state is unknown
            - Device.EMPTY: the block is empty
            - RComBlkDet.BLK_OCC: the block is occupied, but no RailCom Channel 1 information is available
            - RComBlkDet.BLK_CH1: the block is occupied and RailCom Channel 1 information is available
            """
        return self._blk_state


    def _log_error(self,error_code):
        try:
            self._errors[error_code] += 1
        except KeyError:
            self._errors[error_code] = 1


    def _load_check(self, _):
        """ Load check timer expired callback

        Check to see if there's a load on the block.
        """
        #Device.check_core0()
        if self._enable_pin is None or self._enable_pin() == 1:
            # only check if we have power!

            if self._rx_pin() == 1:
                # no load
                if self._no_resp_count < 0:
                    if self._blk_state[0] != RComBlkDet.BLK_EMPTY: 
                    # consecutive missed response limit reached
                    # but it's not been reported
                        self._id_val = {} # clear any previous datagrams
                        self._last_report = None
                        self._blk_state = (RComBlkDet.BLK_EMPTY, None)
                        self.report_event(*self._blk_state)
                else:
                    self._no_resp_count -= 1
            else:
                # false positive unlikely so report change immediately if was empty
                # but allow limit misreads if last report was CH1 data
                if self._blk_state[0] not in (RComBlkDet.BLK_OCC, RComBlkDet.BLK_CH1):
                    # either empty or start of day
                    self._no_resp_count = _MAX_NO_READ
                    self._blk_state = (RComBlkDet.BLK_OCC, None)
                    self.report_event(*self._blk_state)
                elif self._blk_state[0] == RComBlkDet.BLK_CH1:
                    if self._no_resp_count < 0:
                        # consecutive limit reached
                        self._id_val = {}
                        self._last_report = None
                        self._blk_state = (RComBlkDet.BLK_OCC, None)
                        self.report_event(*self._blk_state)
                    else:
                        self._no_resp_count -= 1
                else:
                    self._no_resp_count = _MAX_NO_READ  # reset the count

                
        # start timer for next check
        self._load_timer.init(mode = Timer.ONE_SHOT, period = _TIMER_PERIOD, callback = self._load_check)
        
  
    def _rail_com_ch1_msg(self,  buffer, orientation):
        """ This callback is called on termination of the RailCom Channel 1 message receipt window,
        whether a message has been received or not. Any decoder on the associated block returns a channel 1
        message. 

        args:
            self:
            buffer:   translated data
            orientation: orientation of DCC decoder wrt DCC signal
        """

        # detector_side 1 or -1, 0 nothing detected.
        if orientation == 0:
            # do nothing at the moment
            # not logged as error - may be nothing there
            return
        # there must be at least one 1 byte there
        if buffer[0] == RailComRead.ERR_OE:
            # first character has overrun - most likely switching noise after end of window
            # not logged
            return

        try:
            if buffer[1] == RailComRead.ERR_OE:
                self._log_error('oe') # overrun on in datagram
            if buffer[0] == RailComRead.ERR_WH or buffer[1] == RailComRead.ERR_WH:
                self._log_error('wh')  # hamming code look up error detected earlier
            if buffer[0] == RailComRead.ERR_WL or buffer[1] == RailComRead.ERR_WL:
                self._log_error('wl')  # hamming code look up error detected earlier
                return

            if buffer[0] > 0x3f or buffer[1] > 0x3f:
                self._log_error('ic') # channel 1 datagrams cannot include control bytes
                return
        except IndexError:
            # datagram too short
            self._log_error('df') # log as datagram format error
            return

        # both values need to be present to get this far
        # there's a valid response so reset the 'no response' count
        self._no_resp_count =  _MAX_NO_READ
        # and restart the load check timer
        self._load_timer.init(mode = Timer.ONE_SHOT, period = _TIMER_PERIOD, callback = self._load_check)

        # save the payload value against the id
        dg_id = buffer[0] >> 2
        self._id_val[dg_id] =  ((buffer[0] & 0x03) << 6) | buffer[1]

        # track datagrams by type
        self._dgs.add(dg_id)
  

        # try and build decoder address
        try:
            if self._id_val[1] == 0:
            # short address
                address_type = 's'
                address = self._id_val[2]
            elif self._id_val[1] == 0x60:
                # consist address
                address_type = 'c'
                address = self._id_val[2]
            elif (self._id_val[1] & 0xc0) == 0x80:
                # long address
                address_type = 'l'
                address = (self._id_val[1] & 0x3f) << 8 + self._id_val[2]
            else:
                # ID1 content invalid - ignore
                return
        except KeyError:
            # missing id 1 or id 2
            # insufficient info - there may be enough next time!
            return
        
        # if the occupancy report has changed since the last time
        # report the event and update saved info for next time.
        report_data = (address_type, address, orientation)
        if report_data != self._blk_state[1]: # occupancy info changed?
            self._blk_state = (RComBlkDet.BLK_CH1, report_data)
            self.report_event(*self._blk_state)
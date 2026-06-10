"""DCC Block Current Detection
    :author: Paul Redhead

This module contains the functions and classes for DCC block detection
based on current load monitoring. This is for the resistor based detector where the
ADC is on the track side of the galvanic isolation and uses a TI ADC1015 ADC rather than the
Pico's own ADC.
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

from machine import I2C

from device import Device
from hw_conf import HwConf

_TIMER_PERIOD = const(50)   # time in ms between checks for current load on block

# The characteristic time constant for a simple infinite impulse response digital
# filter is 𝞃 = -1/ln(d) where d is the filter ratio.
# A ratio of 0.8 
# in conjuntion with a 50 ms period gives a characteristic time of c. 0.22s for
# signal filter.
# This is equivalent to the CR time constant of a simple analogue low pass filter.
_FILTER_FACTOR = const(5)   # IIR filter factor (reading)
_FILTER_RATIO =  const((_FILTER_FACTOR - 1) / _FILTER_FACTOR)

# In conjuntion with a 50 ms period this gives a characteristic time of c. 5s for
# zero reference filter.
_Z_FILTER_FACTOR = const(100)   # IIR filter factor (zero offset)
_Z_FILTER_RATIO =  const((_Z_FILTER_FACTOR - 1) / _Z_FILTER_FACTOR)

_U_THRESHOLD = const(150) # 
_L_THRESHOLD = const(75) #
_U_LIMIT = const(_U_THRESHOLD * 3 // 2) # upper limit value

# ADC1015 parameters to start read.
# 
_ADC_CONF0 = b'\x95\xE3' # Single read, mux 1, FSR 2048 mV, 3300 sps, comparator off
_ADC_CONF1 = b'\xA5\xE3' # as above but mux 2
_ADC_CONF0C = b'\x14\xE3'# mux 1 continuous read
_ADC_CONF1C = b'\x24\xE3'# mux 2 continuous read

_ADC_CONF_ADD = const(1)
_adc_addr = {0: (72, _ADC_CONF0, _ADC_CONF0C),
             1:(72, _ADC_CONF1, _ADC_CONF1C),
             2: (73, _ADC_CONF0, _ADC_CONF0C),
             3:(73, _ADC_CONF1, _ADC_CONF1C)}
_i2c = I2C(1)


class DCCBlkDet(Device):
    """DCC (block current) Detector
    
    This runs on a local block detector MCU.

    In addition to interpreting channel 1 messages elsewhere, we monitor
    the block for occupancy, detecting non RailCom decoders and other loads.
    E.g coaches with lighting etc. This detection uses the same raw hardware
    detection as the RailCom channel 1 detector, but the signal is processed
    differently within the detector hardware and interpreted differently
    here.

    The RailCom output from the detector is a digital signal, whereas this
    uses an analog output from the detector.
    
    The detected current is amplified within the detector such that 1mA of
    track current appears at the analog input as cf * gain mV where cf is
    the track current to detector conversion factor (1.8) and gain (100) is the
    gain of the detector op. amp. This equates to 1mA => 180 mV.  The signal
    is centred around a nominal 0V.
    
    The op. amp. runs on 5 V and its outputs will saturate at about ± 14mA 
    of input current. If using resistor wheel sets, a typical value is 10 kΩ
    and thresholds can be set at c. 1mA to detect these.

    This inherits from the Device Class.

    Block status may be:
        - empty
        - occupied
        - unknown (start of day)
        - unpowered (no DCC power)

    Attributes:
        DEVICE_TYPE: 'd' for (current) detector
    """



    _i2c_lock = asyncio.Lock() # to ensure only one read at a time

    def __init__(self, blk_name, i):
        """Construct the block current detector
        
        This constructs the block current detector.

        The base Device class is initiated with the block name and type.
        Inititial values are set.

        args:
            blk_name: the name of the block
            i: logical block number
        """

        
        self._id_val = {} # channel 1 payload values for ids 1 & 2
        self._index = i #
        self._av = 0.0 # initialise average IIR filtered reading with start value
        self._offset = 0.0 

        """block state may be unknown, empty, occupied"""
        self._blk_state = Device.UNKNOWN # start of day value
       
        self._ready_flag = asyncio.ThreadSafeFlag() # used to signal new state available to comms agent

        super().__init__(blk_name,
                        Device.BD_DEV_TYPE)
        
        asyncio.create_task(self._monitor())

    async def wait_for_flag(self):
        """ Wait for the new state available event

        This waits for the asynchio event to be set.
        """
        await self._ready_flag.wait()
        return
    
    @property
    def index(self):
        return self._index # this is the logic index number too

    def report_event(self, event, data):
        """ Report Event
        
        This overrides the Device.report_event method.
        It sets the event flag to indicate block status change.
        
        args:
            event:  updated Block status code.
            data:   a tuple containing address type, address & orientation  
        """
        self._ready_flag.set()
        super().report_event(event, data)

    def get_sensor_state(self):
        """ Get the current block state
        
        This returns the current sensor state. 
        The block status may be:
        - Device.UNKNOWN: the block state is unknown
        - Device.BLK_EMPTY: the block is empty
        - Device.BLK_OCC: the block is occupied
        """
        return self._blk_state
    
    async def _get_reading(self):
        """Get Reading Pair

        We take a set of raw readings. Currently hard coded at ten.  Raw readings may be +ve or -ve.
        The set is processed to determine the absolute maximum value relative to the zero offset.
        We also determine the average value.  This is used to determine the zero offset.
    
        Both values are returned.
        """
        def _adc2int(adc_res):
            """ this is a 12 bit signed (2's comp) value in two bytes but left aligned.  L.S 4 bits always 0
            It's converted to a signed integer"""
            v = (adc_res[0] << 4) + (adc_res[1] >> 4)
            if (adc_res[0] & 0x80):
                v = ((~v & 0x0fff) + 1) * -1
            return(v)
        
        i2c_addr, sngl_conf, cont_conf = _adc_addr[self._index]

        async with DCCBlkDet._i2c_lock:
            try:
                _i2c.writeto_mem(i2c_addr,_ADC_CONF_ADD,sngl_conf) # single start read
                # this will flush any earlier readings from the result register
                while True:
                    # let other stuff run
                    asyncio.sleep_ms(0)
                    if (_i2c.readfrom_mem(i2c_addr,_ADC_CONF_ADD, 2)[0] & 0x80):
                        break   # we have a result
                _i2c.writeto_mem(i2c_addr,_ADC_CONF_ADD,cont_conf) # switch to continuous reads
                # read reg 0 (result register) 10 times (results may not be unique!)
                # we can read the results register faster than the sampling rate!
                readings = [_adc2int(_i2c.readfrom_mem(i2c_addr, 0, 2)) for _ in range (0,10)]
                _i2c.writeto_mem(i2c_addr,_ADC_CONF_ADD,b'\x03\x01') # sleep
            except OSError:
                # i2c error - no track power most likely
                return (None, None)
        max_v = max([abs(v - int(self._offset + 0.5)) for v in readings]) # value for determining occupancy
        set_v = set(readings) # value for calculating 0 offset - remove duplicates 
        return (max_v, sum(set_v)/len(set_v)) # return abs max & average
 
    async def _monitor(self):
        """ Coroutine to monitor current 

        This periodically reads the current sense analog input pin.

        The readings are processed to derrive two values.

        Firstly the base value representing 0 current is obtained.  This
        assumes that over a period of time that is sufficiently long compared
        with the DCC frequency and other periodic factors, the net current flow
        is zero. I.e there is no DC component in the current flow. Note that
        RailCom doesn't permit '0' stretching. 
        The readings are filtered using a low pass Infinite Impulse
        Response (IIR) digital filter and the result is taken as being the zero
        offset. In theory the DCC signal measurement now uses a differential
        ADC so the offset should be 0 but in practice a small offset remains,
        possibly due to an offset error in the analogue amplifier.

        Secondly the value representing the current load is calculated.
        The input to this is the magnatude of the difference between the
        zero offset value and the reading. I.e. the absolute value without
        sign. The reading sampling runs asynchronously with respect to DCC
        and RailCom cutout timings. Atypically low values are assumed to be
        samples taken at DCC polarity change or during the RailCom cutout.

        The filtered values are compared with two thresholds to determine
        whether the block is occupied. The thresholds apply hysterisis to
        avoid hunting.

        The coroutine task runs forever.
        """
        while True:
            await asyncio.sleep_ms(_TIMER_PERIOD)
            reading, av_reading = await self._get_reading()
            if reading is None:
                # no power
                if self._blk_state != Device.BLK_NPOW:
                    self._blk_state = Device.BLK_NPOW
                    self.report_event(Device.BLK_NPOW, None)
            else:
                # update offset
                self._offset = self._offset * _Z_FILTER_RATIO + av_reading / _Z_FILTER_FACTOR
                # an increase is taken immediately but limited to the upper limit
                # a decrease is subject to IIR decay
                if reading > self._av:
                    self._av = min(reading, _U_LIMIT)
                else:
                    # apply IIR low pass filter
                    self._av = self._av * _FILTER_RATIO + reading / _FILTER_FACTOR
                # check against thresholds
                if self._blk_state != Device.BLK_OCC and self._av > _U_THRESHOLD:
                    self._blk_state = Device.BLK_OCC
                    self.report_event(Device.BLK_OCC, None)
                elif self._blk_state != Device.BLK_EMPTY and self._av < _L_THRESHOLD:
                    self._blk_state = Device.BLK_EMPTY
                    self.report_event(Device.BLK_EMPTY, None)


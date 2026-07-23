"""Track & Booster Monitor Module
    :author: Paul Redhead

This module contains the class and functions for monitioring track / booster status and updating NeoPixel accordingly.

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

from micropython import const
import time
from led_pio import NeoLed
from hw_conf import HwConf


class TrkMon:
    """ Monitor Track and Booster Power State

    DRV8874 fault may be:
    - over current trip
    - under volage on VM or charge pump
    - over temperature

    Current Sense

    The DRV8874 current sense pin is a current source that produces 450 µA/A of output current. The load
    resistor on the Pololu board is 2.49 kΩ. I.e .45 mA * 2.49kΩ  => 1.1205 V at the sense pin per amp
    output. The over current circuit will trip when sense pin V is c. 3.3 V - it's the logic high (false)
    level at _sleep. => 2.95 A. However the continuous rating for the DRV8874 as mounted on the Pololu board
    is 2.1 A.

    The sense reading is a 16 bit number with 65535 corresponding to 3.3 volts.  We set thresholds at 1A and 2A.

    The thresholds are used to set the NeoPixel colour:
    - < 1A = pure green
    - < 2A = yellowish
    - > 2A = orange
    The DCC monitor is a singleton class that monitors the DCC status and updates the NeoPixel
    accordingly. It uses a statistical median filter and an Infinite Impulse Response (IIR) filter to smooth the current sense reading
    and the zero offset to remove the zero offset when the DCC is asleep. The statistical median
    filter is non linear and removes outlying values.The IIR filter is
    implemented using a simple formula:

        new_value = (old_value * (FILTER_FACTOR - 1) /FILTER_FACTOR + (new_reading / FILTER_FACTOR)
    
    where FILTER_FACTOR is a constant that determines the amount of filtering applied.
    The zero offset is calculated when the DCC is asleep and is used to remove the zero
    offset from the current sense reading when the DCC is awake. The zero offset is also
    filtered using the same IIR filter formula.

    This code is intended to run on the second core (core1) and cannot use preemptive code such as
    timer callbacks or interrupts.

    Attributes:
        FILTER_FACTOR: The IIR filter factor for reading.
        FILTER_RATIO: The IIR filter ratio ((filter factor - 1)/filter factor)
        Z_FILTER_FACTOR: IIR filter factor for zero offest
        Z_FILTER_RATIO: The 0 offset filter ratio ((filter factor - 1)/filter factor)
        THRESHOLD_1: The threshold for 1A in the current sense reading.
        THRESHOLD_2: The threshold for 2A in the current sense reading.
        DRV_CURRENT_RATIO: convert the raw sensor reading to current in mA.
        STAT_MEDIAN_SIZE: The size of the statistical median filter (must be odd).
        STAT_MEDIAN_INDEX: The index of the median value within the value list.
        SCAN_INTERVAL: The time interval between scans in ms.
        BRIGHT: NeoLed default brightness.
    """

    _this_mon = None # the singleton DCC monitor instance

    STAT_MEDIAN_SIZE = const(5) # size of statistical median filter (must be odd)
    STAT_MEDIAN_INDEX = const(STAT_MEDIAN_SIZE // 2) # index for median value
    FILTER_FACTOR = const(10)   # IIR filter factor (reading)
    FILTER_RATIO =  const((FILTER_FACTOR - 1) / FILTER_FACTOR)

    Z_FILTER_FACTOR = const(100)   # IIR filter factor (zero offset)
    Z_FILTER_RATIO =  const((Z_FILTER_FACTOR - 1) / Z_FILTER_FACTOR)

    SCAN_INTERVAL = const(100)  # time between scans in ms

    THRESHOLD_1 = const(65535 / 3.3)
    THRESHOLD_2 = const(THRESHOLD_1 * 2)

    DRV_CURRENT_RATIO = const(3300 / (0.45 * 2.49 * 65535))  #mA per unit ADC read

    BRIGHT = const(12) # default brightness

    @classmethod
    def get_instance(cls):
        """ Get the Track Monitor instance.

        This returns the singleton instance of the Track/Booster Monitor.

        Instantiate the singleton on the first call.

        Args:
            cls:

        Returns:
            The Track monitor instance
        """
        if cls._this_mon is None:
            TrkMon()
        return cls._this_mon
    
    def __init__(self):
        """ Initialise the Track Monitor

        This initialises the Monitor with the pins that it will use to monitor the DCC status.
        
        Reads the following from hardware configuration
            _sleep_pin: The pin that is low when the DRV8874 is asleep.
            _enable_pin: The pin that is high when the DRV8874 is enabled.
            _fault_pin: The pin that is low when there is a fault.
            _sense_pin: The pin that reads the current sense voltage.
        """
        assert TrkMon._this_mon is None, 'only one instance allowed'
        TrkMon._this_mon = self
        self._enable_pin, self._fault_pin, self._sleep_pin, self._sense_pin = HwConf.get_instance().trk_pins
        self._next_run_time = 0 # time in ms for the next scan
        # initialise IIR filters
        self._sense = 0.0
        self._sense_zero = float(self._sense_pin.read_u16())
        # initialise the NeoPixel LED
        self._led = NeoLed(NeoLed.DCC_LED)
        self._readings = [self._sense_pin.read_u16() for _ in range(TrkMon.STAT_MEDIAN_SIZE)]

    def scan(self):
        """ Scan the DCC status and update the NeoPixel accordingly.
        
        This scans the DCC status and updates the NeoPixel accordingly. 
        This method is called periodically to update the DCC status and NeoPixel.
        It checks the fault pin, sleep pin, and enable pin to determine the DCC
        status and updates the NeoPixel accordingly. If the fault pin is low,
        it indicates a fault condition and the NeoPixel is set to blue. If
        the sleep pin is low, it indicates that the DCC is asleep and the
        current sense reading is updated to the zero offset. If the enable
        pin is low, it indicates that the DCC is in a cutout condition and
        the NeoPixel is set to blue if the fault pin is low, otherwise it is
        set to red.
        
        If the DCC is awake, the current sense reading is updated and the
        NeoPixel is set to green, yellowish, or orange depending on the current sense reading.
        The NeoPixel is updated with the appropriate RGB values based on the
        current sense reading.
        
        The method also updates the next run time to be 100 ms in the future.
        """
        if not self._fault_pin():
            # fault condition - acted on immediately
            # if enable is true assume it's overcurrent but if 
            # enable is false then we're in a cutout and it must be one of the 
            # other conditions - add blue to indicate this
            if not self._enable_pin():
                self._led.set(NeoLed.LED_B, False, val = TrkMon.BRIGHT)
            self._led.clear(NeoLed.LED_G,False)
            self._led.set(NeoLed.LED_R, val = TrkMon.BRIGHT)
            time.sleep_us(50) # allow for string transmission termination time
            return
        
        ts = time.ticks_ms()
        if time.ticks_diff(self._next_run_time,ts) > 0:
            # not time for next run yet
            return
        # get reading and apply statistical median filter
        self._readings.append(self._sense_pin.read_u16())
        if len(self._readings) > TrkMon.STAT_MEDIAN_SIZE:
            self._readings.pop(0)
        f_reading = sorted(self._readings)[TrkMon.STAT_MEDIAN_INDEX]

        if not self._sleep_pin():
            # power off (asleep) so no current - update the zero reference 
            self._sense_zero = ((self._sense_zero * TrkMon.Z_FILTER_RATIO)
                + (f_reading / TrkMon.Z_FILTER_FACTOR))
            self._sense = 0.0
            self._led.clear(NeoLed.LED_B, False)
            self._led.clear(NeoLed.LED_G, False)
            self._led.clear(NeoLed.LED_R)
        else:
            # update the filtered reading
            current = f_reading - self._sense_zero
            self._led.clear(NeoLed.LED_B, False)
            self._sense = ((self._sense * TrkMon.FILTER_RATIO)
                            + (current / TrkMon.FILTER_FACTOR))
            if self._sense < TrkMon.THRESHOLD_1:
                # pure green
                self._led.clear(NeoLed.LED_R, False)
                self._led.set(NeoLed.LED_G, val = TrkMon.BRIGHT)            
            elif self._sense < TrkMon.THRESHOLD_2:
                # yellowish
                self._led.set(NeoLed.LED_R, False,  val = TrkMon.BRIGHT // 3)
                self._led.set(NeoLed.LED_G, val = (TrkMon.BRIGHT * 2 // 3))      
            else:
                # more orange
                self._led.set(NeoLed.LED_R, False,  val = (TrkMon.BRIGHT * 2) // 3)
                self._led.set(NeoLed.LED_G, val = (TrkMon.BRIGHT // 3))      
        self._next_run_time = time.ticks_add(ts, 100) # next run in 100 ms

    def get_current(self):
        """ Get the current

        Returns:
            the current as derrived from the DRV8874 current sense pin in mA
        """
        return TrkMon.DRV_CURRENT_RATIO * (self._sense)

"""DCC Monitor Module
    :author: Paul Redhead

This module contains the class and functions for monitioring DCC status and updating NeoPixel accordingly.

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

from micropython import const
import time
from led import NeoString, Led


class DCCMon:
    """ Monitor DCC Power

    DEV8874 fault may be:
    - over current trip
    - under volage on VM or charge pump
    - over temperature

    Current Sense

    The DRV8874 current sense pin is a current source that produces 450 µA/A of output current. The load
    resistor on the Pololu board is 2.49 kΩ. I.e 1.1205 V at the sense pin per amp output. The over
    current circuit will trip when sense pin V is c. 3.3 V - it's the logic high (false) level 
    as _sleep. c. 2.9 amps. However the continuous rating for the DRV8874 as mounted on the Pololu board
    is 2.1 A.

    The sense reading is a 16 bit number with 65536 corresponding to 3.3 volts. To increase precision
    for filtering we multiply numbers by 10.  We set thresholds at 1A and 2A.

 
    The thresholds are used to set the NeoPixel colour:
    - < 1A = pure green
    - < 2A = yellowish
    - > 2A = orange
    The DCC monitor is a singleton class that monitors the DCC status and updates the NeoPixel
    accordingly. It uses an IIR filter to smooth the current sense reading and a zero offset
    filter to remove the zero offset when the DCC is asleep. The IIR filter is
    implemented using a simple formula:

        new_value = (old_value * (FILTER_FACTOR - 1) + new_reading) / FILTER_FACTOR
    
    where FILTER_FACTOR is a constant that determines the amount of filtering applied.
    The zero offset is calculated when the DCC is asleep and is used to remove the zero
    offset from the current sense reading when the DCC is awake. The zero offset is also
    filtered using the same IIR filter formula.

    Attributes:
        _this_mon: The singleton instance of the DCC monitor.
        FILTER_FACTOR: The IIR filter factor for both zero offset and reading.
        THRESHOLD_1: The threshold for 1A in the current sense reading.
        THRESHOLD_2: The threshold for 2A in the current sense reading.
        LED_B: The default brightness of the NeoPixel LED.
    
    """

    _this_mon = None # the singleton DCC monitor instance

    FILTER_FACTOR = const(10)   # IIR filter factor (both for zero offset and reading)

    THRESHOLD_1 = 655360 / 3.3
    THRESHOLD_2 = THRESHOLD_1 * 2

    LED_B = 12 # default brightness


    @classmethod
    def get_instance(cls):
        """ Get the DCC Monitor instance.

        This returns the singleton instance of the DCC Generator.

        Args:
            cls:

        Returns:
            The DCC generator instance
        """
        return cls._this_mon
    

    def __init__(self, sleep_pin, enable_pin, fault_pin, sense_pin):
        """ Initialise the DCC Monitor

        This initialises the DCC Monitor with the pins that it will use to monitor the DCC status.
        
        Args:
            sleep_pin: The pin that is low when the DCC is asleep.
            enable_pin: The pin that is high when the DCC is enabled.
            fault_pin: The pin that is low when there is a fault.
            sense_pin: The pin that reads the current sense voltage.
    
        """
        if (DCCMon._this_mon is not None):
            raise RuntimeError('only one instance allowed')
        DCCMon._this_mon = self
        self._next_run_time = 0 # time in ms for the next scan
        self._sleep_pin = sleep_pin # low for true - high for track power on
        self._enable_pin = enable_pin # high for true - low for RailCom cutout in progress
        self._fault_pin = fault_pin # low for true - high for no fault
        self._sense_pin = sense_pin # analogue input
        # initialise IIR filters
        self._sense = self._sense_zero = sense_pin.read_u16() * DCCMon.FILTER_FACTOR
        self._filter_ratio =  ((DCCMon.FILTER_FACTOR - 1) / DCCMon.FILTER_FACTOR)
        # initialise the NeoPixel LED
        self._led = NeoString.get_instance().get_led(Led.DCC_LED)


    def scan(self):
        """ Scan the DCC status and update the NeoPixel accordingly.
        
        This scans the DCC status and updates the NeoPixel accordingly. 
        This method is called periodically to update the DCC status and NeoPixel.
        It checks the fault pin, sleep pin, and enable pin to determine the DCC status
        and updates the NeoPixel accordingly. If the fault pin is low, it indicates a fault
        condition and the NeoPixel is set to blue. If the sleep pin is low, it indicates that the DCC is asleep
        and the current sense reading is updated to the zero offset. If the enable pin is low,
        it indicates that the DCC is in a cutout condition and the NeoPixel is set to blue if the fault pin is low, otherwise it is set to red.
        If the DCC is awake, the current sense reading is updated and the NeoPixel is set to green, yellowish, or orange depending on the current sense reading.
        The NeoPixel is updated with the appropriate RGB values based on the current sense reading.
        The method also updates the next run time to be 100 ms in the future.
        
        """
        if self._fault_pin() == 0:
            # fault condition - acted on immediately
            # if enable is true assume it's overcurrent but if 
            # enable is false then we're in a cutout and it must be one of the 
            # other conditions - add blue to indicate this
            self._led.set_rgb((DCCMon.LED_B, 0,
                              DCCMon.LED_B if self._enable_pin() == 0 else 0))
            time.sleep_us(100) # allow for string transmission termination time
            return
        
        ts = time.ticks_ms()
        if time.ticks_diff(self._next_run_time,time) > 0:
            # not time for next run yet
            return
        if self._sleep_pin() == 0:
            # power off (asleep) so no current - update the zero reference 
            self._sense_zero = self._sense_zero * self._filter_ratio + self._sense_pin.read_u16()
            self._led.set_rgb((0, 0, 0))
        else:
            # update the current reading
            self._sense = self._sense * self._filter_ratio + self._sense_pin.read_u16()
            sense = self._sense - self._sense_zero
            if sense < DCCMon.THRESHOLD_1:
                # pure green
                rgb = (0, DCCMon.LED_B, 0)  # pure green for < 1A               
            elif sense < DCCMon.THRESHOLD_2:
                # yellowish
                rgb = (DCCMon.LED_B // 3, (DCCMon.LED_B * 2) // 3, 0)
            else:
                # more orange
                rgb = ((DCCMon.LED_B * 2) // 3, DCCMon.LED_B // 3, 0)
            self._led.set_rgb(rgb)
        self._next_run_time = time.ticks_add(ts, 100) # next run in 100 ms
        
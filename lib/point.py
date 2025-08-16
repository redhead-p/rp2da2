"""Point Module

This module provides the base class for a point (aka turnout).
"""
"""       Copyright 2025  Paul Redhead

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""

from micropython import const
from machine import I2C, Timer

from device import Device

_PCF8574_BASE = const(0x20) # PCF8574 base address



class MPPointDriver():
    """ MTB MP Point Driver
    
    MTB MP point motors are driven using a pair of low side switches. This drives
    points where the low side drivers are connected via I2C or SPI.  This test version
    uses a PFC8574 in conjuction with a ULN2803 or similar. One of the pair of switches is
    energised at a time.

    This driver is a singleton.  If more than 4  points are required, then a second PFC8574
    would be required on the I2C interface.

    I2C(0) is used in common with the OLED screen and like the OLED screen driver, this
    runs on core1.  Commands are passed from core0 via the Device event queue.
    """

    CMD_DECODE = {'N':(1, True), # Normal  output on
                  'R':(2, True), # Reverse output on
                  ' ':(3, False), # both off
                 }
    
    _mp_driver = None


    @classmethod
    def get_instance(cls):
        """Return the singleton instance

        The singleton is created on the first call. It is only created if it's possible.
        I.e. on an Arduino Nano RP2

        args:
            cls:
        """
        if cls._mp_driver is None:
            cls._mp_driver = MPPointDriver()        
        return cls._mp_driver


    def __init__(self):
        if (MPPointDriver._mp_driver) != None:
            raise RuntimeError('only one instance allowed')
        self._i2c = I2C(0) # I2C 0 is shared with the OLED display.
        # check for likely PCF8574 chips
        self._valid_addr = [a for a in self._i2c.scan() if 0x20 >= a <= 0x27]
        self._cmd_byte = bytearray(b'\x00') # buffer for i2c write

    def set_to(self, report):
        (_, instruction, data) = report
        if instruction != Device.TO_CMD:
            return  False  # not me
        num, target_state = data
        i2c_ad = num // 4 + _PCF8574_BASE
        try:
            output, output_on = self.CMD_DECODE[target_state]
        except KeyError:
            return False
        
        self._cmd_byte[0] &= ~(3 << ((num % 4) * 2)) # switch off both
        # and switch on the one we wane
        if output_on:
            output <<= (num % 4) * 2  # shift to position
            self._cmd_byte[0] |= output
        return self._i2c.writeto(i2c_ad, self._cmd_byte) == 1

class Point(Device):
    """This is the Point base class

    It holds the point state.

    Attributes:
        UNAVAIL:    server disconnected (only applicable to client)
        UNKNOWN:    state unknown (e.g. start of day)
        INDETERMINATE:  command being actioned or sensors (if any) inconsistent
        NORMAL:     Normal (closed) - typically set straight
        REVERSE:    Reverse (thrown) - typically set divergent

    
    """
    # static constants
    # point state (would be enum but enum not available in MicroPython)
    UNAVAIL = const(0)
    UNKNOWN = const(1)
    INDETERMINATE = const(2)
    NORMAL = const(3) 
    REVERSE  = const(4)
    CMD_DECODE = {'N':NORMAL, 'R':REVERSE}

    def __init__(self, name):
        
    
        self._state = Point.UNKNOWN       # unknown until a move is initiated
        self._target_state = Point.UNKNOWN # needs to be same as state initially
        self._name = name               # system name of point
        
    def set_state(self, new_state):
        """ Update the Point state
        
        This updates the internal copy of the point's state.
        
        args:
            self:
            new_state: the new state
            """
        self._state = new_state
        


    def get_state(self):
        return(self._state)
    
    def set_position(self, cmd):
        """Set Point Position
        
        This must be defined in the inheriting class.
        
        args:
            self:
            cmd: new position ('N' or 'R')"""
        raise NotImplementedError
    
class MPPoint(Point):

    MOVE_TIME = const(3000) # allow 3 seconds for move


    def __init__(self, name, number):
        self._number = number           # local hardware number
        self._move_timer = Timer()      # create a timer - initialised later
        super().__init__(name)


    def set_position(self, cmd):
        """Set Point Position
        
        This overrides point.set_position
        
        args:
            self:
            cmd: new position ('N' or 'R')
        """
        # send command to driver
        self.report_event(Device.TO_CMD,(self._number, cmd))
        try:
            self._target_state = Point.CMD_DECODE[cmd]
        except KeyError:
            pass # ignore invalid command - target state not changed
        self.set_state(Point.INDETERMINATE) # while point moving
        # set a timer to allow for point to move
        self._move_timer.init(mode = Timer.ONE_SHOT,
                            period = MPPoint.MOVE_TIME,
                            callback = self._move_complete)
        
    def _move_complete(self, _):
        # point move should be complete by now - turn motor off
        self.report_event(Device.TO_CMD,(self._number, ' '))
        self.set_state(self._target_state)

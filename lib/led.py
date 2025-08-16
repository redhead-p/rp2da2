"""LED Module

This module provides the classes for the driving string connected LEDs such as NeoPixel etc.
It also includes driving the tricolour LED on the Arduino Nano RP2040 connect.

Each string is driven by a single GPIO pin.  We use NeoPixels as on board indicators and as such
we only expect a short string of LEDs and there will only be one string per board.

The Arduino LED is driven by GPIO Pins on the wireless radio module rather than on the RP2040 itself.

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

from machine import Pin
from micropython import const
from neopixel import NeoPixel
from device import Device

class Led:
    """Base class for LED control  

    This class provides the base functionality for controlling LEDs.
    It is not intended to be used directly but rather as a base class for specific LED implementations.
    The LED colours are defined as constants:

    Attributes:
        LED_R: Red
        LED_G: Green
        LED_B: Blue
"""
    LED_R = const(0)
    LED_G = const(1)
    LED_B = const(2)

    COMMS_LED = 0
    DCC_LED = 1


class TriLed(Led):
    """ Tricolour Led
    
    This drives a RGB led as fitted on the Arduino Nano RP2040 Connect. It will not instantiate on
    Pico variants.

    This is a singleton class.  The get_instance() method returns the singleton instance.
    If the instance does not exist it is created on the first call to get_instance().
    The LED is controlled by three GPIO pins, one for each colour.  The colours are
    Red, Green and Blue.  The colours are set by calling the set() method with
    TriLed.LED_R, TriLed.LED_G or TriLed.LED_B as the argument.
    The colours are turned off by calling the clear() method with the same arguments.

    N.B it appears that this must run on core 0 - the same as the network. It's not thread safe
    to run on core 1. 
    """

    _tri_led = None

    @classmethod
    def get_instance(cls):
        """Return the singleton instance

        The singleton is created on the first call. It is only created if it's possible.
        I.e. on an Arduino Nano RP2

        If the Led pins are invalid then it's assumed we are on
        a Pico and the tricolour Led is not there.
        args:
            cls:
        """
        if cls._tri_led is None:
            try:
                cls._led_lu = {TriLed.LED_R:Pin('LEDR', Pin.OUT),
                        TriLed.LED_G:Pin('LEDG', Pin.OUT),
                        TriLed.LED_B:Pin('LEDB', Pin.OUT)}
                cls._tri_led = TriLed()
            except ValueError:
                # one of the pin names not available
                pass
        return cls._tri_led
    
    def __init__(self):
        """Initialise the TriLed class

        This initialises the GPIO pins for the LED.  The pins are set to output mode.
        If the singleton already exists then an exception is raised.
        """
        if (TriLed._tri_led) != None and (TriLed._tri_led is not self):
            raise RuntimeError('only one instance allowed')
        

        
    def set(self, colour, value = 1):
        """Set the colour of the LED

        This sets the colour of the LED by setting the GPIO pin to high.

        A value of > 0 indicates led on. 0 led off.  This is inverted at the pin which is 0 for on.
        args:
            colour: The colour to set.  This should be one of TriLed.LED_R, TriLed.LED_G or TriLed.LED_B.
        """
        try:
            self._led_lu[colour].value(0 if value > 0 else 1)
        except KeyError:
            # quietly ignore invalid colour
            pass

    def clear(self, colour):
        """Clear the colour of the LED  

        This clears the colour of the LED by setting the GPIO pin to low.
        args:
            colour: The colour to clear.  This should be one of TriLed.LED_R, TriLed.LED_G or TriLed.LED_B.
        """
        try:
            self._led_lu[colour].value(1)
        except KeyError:
            # quietly ignore invalid colour
            pass



class NeoLed(Led):
    """ NeoPixel Led
    
    This class controls a single LED on the chain.

    RGB values may either be passed as a tuple or a single colour may be set or cleared.

    Setting a colour without a value will set the maximum(255).  Clearing a colour will set 0.

    """

    DEFAULT_B = const(50) # full brightness is rather bright!



    
    def __init__(self, led_string, string_index):
        """Initialise the NeoPixel class

        This sets the initial RGB.

        args:
            led_string: The NeoPixel string to which this LED belongs.
            string_index: The index of the LED in the string.


        """
        self._rgb = [0, 0, 0]   # set initial RGB values.
        self._string = led_string # this is the neopixel string
        self._i = string_index
        self.set_rgb(tuple(self._rgb))



        
    def set(self, colour, val = DEFAULT_B):
        """Set the colour of the LED

        This sets the colour and brightness value.
        args:
            colour: The colour to set.  This should be one of NeoLed.LED_R, NeoLed.LED_G or NeoLed.LED_B.
            val: The value to set the colour to.  This should be an integer between 0 and 255.
                 If not specified, it defaults to NeoLed.DEFAULT_B.
        """
        try:
            self._rgb[colour] = val
            self.set_rgb(tuple(self._rgb))  
        except KeyError:
            # quietly ignore invalid colour
            pass

    def clear(self, colour):
        """Clear the colour of the LED  

        This clears the colour of the LED by setting the GPIO pin to low.
        args:
            colour: The colour to clear.  This should be one of TriLed.LED_R, TriLed.LED_G or TriLed.LED_B.
        """
        try:
            self._rgb[colour] = 0
            self.set_rgb(tuple(self._rgb))
        except KeyError:
            # quietly ignore invalid colour
            pass

    def set_rgb(self, rgb):
        """Set the RGB value of the LED

        This sets the RGB value of the LED.
        args:
            rgb: A tuple containing the RGB values.  Each value should be an integer between 0 and 255.
        """
        self._string[self._i] = rgb
        self._string.write()


class NeoString(NeoPixel):
    """String of NeoPixels
    
    A singleton class based on the built-in NeoPixel class.
    Although it's a singleton it is explicitly instantiated and get_instance method 
    will not instantiate it automatically.
    This is to allow the string to be created with a specific pin and length.
    The string is a list of NeoLed objects which can be accessed by index.
    The NeoLed objects are used to control the individual LEDs in the string.
    The string is used to control the LEDs on the board.

    If the Arduino tricolour led is available, it's handled independently.
    """

    _this_string = None



    @classmethod
    def get_instance(cls):
        """Return the singleton instance

        If the singleton already exists then it is returned.
        Otherwise None is returned.
        args:
            cls:
        """
        return cls._this_string


    def __init__(self, pin, ps_len):
        """Initialise the NeoPixel string
        
        This initialises the NeoPixel string with the given pin and length.
        If the singleton already exists then an exception is raised.
        args:
            pin: The GPIO pin to which the NeoPixel string is connected.
            len: The length of the NeoPixel string."""
        if NeoString._this_string is None:
            NeoString._this_string = self
        else:
            raise RuntimeError("Only one LED string allowed")
        super().__init__(pin, ps_len)
        tl = TriLed.get_instance()
        offset  =  0 if tl is None else 0
        self._leds = list(range(ps_len + offset)) #list of leds
        if offset == 1:
            self._leds[0] = tl
        for i in range(offset, ps_len):
            self._leds[i] = NeoLed(self, i - offset)

    def get_led(self, index):
        """Get the LED at the given index

        This returns the NeoLed object at the given index.
        args:
            index: The index of the LED in the string.
        """
        if index == -1:
            return TriLed.get_instance()           
        return self._leds[index]
    
    def show_event(self, report):
        """Show an event report
        
        This updates the pixels according to the event.  Other application actions on events are 
        dealt with elsewhere.

        Args:
            self:
            report: a tuple containing the reference to the source object, the unique event code see: display
                and additional information - format and content event specific
        """
    
        event = report[1]   # extract the event from the report
        try:
            led_num = self._event_decode[event]
            colour, value = report[2]   
            try:
                self._leds[led_num].set(colour, value)
            except IndexError:
                pass
                

        except KeyError:
            # unrecognised event - ignore
            pass



    _event_decode =    {Device.MC_SET_LED:(Led.COMMS_LED),
                        Device.WF_SET_LED:(Led.COMMS_LED)}
    """A dictionary to decode the events into LED actions.
    """
    








if __name__ == '__main__':
    l = TriLed.get_instance()
    ps = NeoString(Pin(22 if l is None else 5), 2)




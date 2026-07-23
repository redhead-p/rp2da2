"""RP2 command station hardware configuration

:author: Paul Redhead

This defines hardware usage and holds configuration details for
command station/global boards and local detector boards.

It covers the allocation of pin numbers and pio state machines etc.

"""
"""       Copyright 2026  Paul Redhead

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
from machine import Pin, ADC
import sys


class HwConf():
    """ Common Hardware Configuration.
    
    This holds hardware pin allocations etc.
    They are collected here to make clear in a single place
    which hardware elements are in use.

    Pins etc are initialised here to avoid duplicate initialisation.

    This, the base class is a singleton. Only one object may inherit from it.

    It sets up the items which are common to all board types.

    This is an abstract class.

    Attributes:
        OLED_I2C: The oled is on I2C 0 (default GPIO pins 4 & 5).
        NP_SM: NeoPixel State Machine number for RP2040 (Pico, PicoW etc).
        NP_SM_P2: State Machine number for RP2350 (Pico2, Pico2W)

    """
    @classmethod
    def get_instance(cls):
        """ Get the Hardware configuration instance.

        This returns the singleton Common Hardware Config instance.
        Note - this returns the base class for access to common
        asignations.  It won't automatically instantiate.

        The singleton is initiated on the first call to get_instance() of an inheriting
        class, but the singleton reference
        is a base class variable. Once set by the first inheriting class get_instance()
        call, no other inheriting class may be instantiated.

        Returns:
            The base configuration class.
        """
        return cls._hw_conf
    
    _hw_conf = None # singleton hardware command instance

    # class constants

    # common assigments
    OLED_I2C = const(0) # the oled is on I2C 0 (default GPIO pins 4 & 5)
    NP_SM = const(5)    # NeoPixel State Machine number for RP2040 (Pico, PicoW etc) 
    NP_SM_P2 = const(9) # NeoPixel State Machine number for RP2350 (Pico2, Pico2W)

    def __init__(self, name, platform):
        """ HW Configuration Constructor

        Initates the stuff common to all configurations.
        Checks that the platform required matches that available.

        Args:
            name: the text name for display
            platform: the required platform.
        """
        build = sys.implementation._build # get MicroPython build details
        assert build.find(platform) != -1, f"Needs {platform}"
        # NeoPixel driver pin
        self._np_pin = Pin(22)  # NeoPixel string control pin
        self._name = name
        
    @property
    def np_pin(self):
        """ GPIO Pin for NeoPixel chain."""
        return(self._np_pin)
    
    @property
    def name(self):
        """ Configuration name for display."""
        return self._name
    
    @property
    def max_led(self):
        """ Number of Leds"""
        return self._max_led

class HwConfLcl(HwConf):
    """ Hardware configuration for the Quad local PCB.

    This provides the hardware configuration for the Quad Local
    RailCom detector board (RC_LCL_4).
    
    Attributes:
        BLK_I2C: block occupancy is on I2C 1(default GPIO pins 6 & 7)
        MAX_LED: Number of NeoPixels.
    """
    @classmethod
    def get_instance(cls):
        """ Get the Hardware configuration instance.

        This returns the singleton Local Hardware Config instance. The instance is
        created on the first call.

        Returns:
            The DCC Command instance
        """
        if HwConf._hw_conf is None:
            HwConfLcl()
        return cls._hw_conf

    BLK_I2C  = const(1) # block occupancy is on I2C 1(default GPIO pins 6 & 7)
    
    def __init__(self):
        """Construct the Local Configuration.
        
        Define DCC sense pin used for detectiing cutouts and allocate
        pin numbser and state machine number for each local detector."""
        assert HwConf._hw_conf is None, 'only one configurator allowed'
        HwConf._hw_conf = self
        # local detector only

        self._max_led = 5      # Number of NeoPixels.

        # Local detector specific assignments
        # DCC power sense pin
        self._dcc_sense = Pin(27, Pin.IN)
        
        self._rx_pin = [14, 16, 18, 20]  # pin numbers for RailCom RX (orientation is pin + 1)
        self._state_machine = [0, 2, 4, 6]  # state machine numbers for RailCom channel timers
        super().__init__("Quad Lcl", 'PICO2')

    def get_lcl_det(self, i):
        """ Get local detector hardware assignements.
        
        Args:
            i: index number of detector (in range 0 to 3)
            
        returns:
            the pin number for received data and the state machine number"""
        return (self._rx_pin[i], self._state_machine[i])
    
    @property
    def dcc_sense(self):
        """GPIO pin for DCC power on sense."""
        return self._dcc_sense
    

class HwConfGbl(HwConf):
    """ Hardware configuration for the integrated Command Station PCB.

    This provides the hardware configuration for integrated Command Station PCB with booster
    and integrated global RailCom detector (RC_3).
    
    Attributes:
        DCC_STATE_MC: DCC generation - First state machine on PIO 0
        RC2_STATE_MC: RailCom Global detector state machine - 3rd on PIO 1
    """
    DCC_STATE_MC = const(0) # DCC generation - First state machine on PIO 0
    RC2_STATE_MC = const(6) # RailCom Global detector state machine - 3rd on PIO 1


    @classmethod
    def get_instance(cls):
        """ Get the Hardware configuration instance.

        This returns the singleton Command Station/Global Hardware Config instance. The
        instance is created on the first call.

        Returns:
            The configuration instance.
        """
        if HwConf._hw_conf is None:
            HwConfGbl()
        return cls._hw_conf


    def __init__(self):
        """Construct the Command Station/Global Configuration.
        
        Define Global detector receive pin and pins used to interface the 
        DRV8874."""
        assert HwConf._hw_conf is None, 'only one configurator allowed'
        HwConf._hw_conf = self

        self._max_led = 2      # Number of NeoPixels.

        self._c2_rx_pin = Pin(16, Pin.IN)
        
        # DCC configuration
        # These pins are managed by the DCC command module.
        # Other devices use of them is read only.
        self._enable_pin = Pin(18, Pin.OUT, value = 1)  # (DRV8874 enable)
        self._sleep_pin = Pin(19, Pin.OUT, value = 0)   # set sleep mode initially (DRV8874 _sleep)
        self._dcc_pin = Pin(20, Pin.OUT)                # dcc tx out (DRV8874 phase)
        # fault and sense are DRV8874 outputs
        self._fault_pin = Pin(21, Pin.IN, Pin.PULL_UP)  # low for true - Open Drain (DRV8874 _fault)
        self._sense_pin = ADC(Pin(26))                  # current sense input

        super().__init__("CS/RC Gbl", "PICO")

    @property
    def dcc_pins(self):
        """ Pins used for DCC generation (DRV8874)"""
        return(self._enable_pin, self._sleep_pin, self._dcc_pin)
    
    @property
    def rc2_pins(self):
        """ Pins used for RailCom channel 2"""
        return(self._c2_rx_pin, self._enable_pin)
    
    @property
    def trk_pins(self):
        """ Pins used for track state monitor
        
        The usage of these pins for the track monitor is read-only."""
        return(self._enable_pin, self._fault_pin, self._sleep_pin, self._sense_pin)        

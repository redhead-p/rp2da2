"""Wi-Fi Interface Module

This acts as wrapper for the standard micropython network/wi-fi functions.

Network configuration and connection credentials are held in 

/conf/wifi.json

Example content:

{"country": "myCountry", "ssid": "mySSID", "password": "myPassword", "hostname":"myHostName"}

All entries are mandatory. Order is not significant. Alter myxxxxx to match the required configuration.

"""
"""       Copyright 2024, 2025  Paul Redhead

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
from machine import Timer
import network
from device import Device
from led import Led, TriLed


import json


_REOPEN_TIME = const(5000)    # wait 5 seconds 

class WiFi(Device):
    """WiFi Connection
    
    This singleton class manages the WiFi Connection. It connects using the 
    credentials as held in the wifi configuration file.
    The connection is checked every 5 seconds and if the connection is lost, it will attempt to reconnect.
    The LED is set to red when not connected and cleared when connected.
    The LED is controlled by the TriLed class.
    """

    _wi_fi = None  # will be set on intantiation

    DEVICE_TYPE = const('w')


    @classmethod
    def get_instance(cls):
        """Return the singleton instance

        The singleton is created on the first call.

        The connection is initiated and a timer is set up to check the success of the connection. If the
        connect fails or the connection is subsequently lost, reconnection is attempted.
        
        args:
            cls:
            """
        if cls._wi_fi is None:
            cls._wi_fi = WiFi()
        return cls._wi_fi

    def __init__(self) -> None:
        """WiFi Initialiser

        This initialises the WiFi connection using the credentials from the configuration file.
        If the singleton already exists then an exception is raised.
        The LED is set to red if the connection is not established.
        A timer is set up to check the connection every 5 seconds. If the connection is lost,
        it will attempt to reconnect.
        """
        if (WiFi._wi_fi) != None and (WiFi._wi_fi is not self):
            raise RuntimeError('only one instance allowed')
        #self._led = NeoString.get_instance().get_led(NeoString.COMMS_LED)
        self._tri_led = TriLed.get_instance() # this will be None on a Pico
        with open('/conf/wifi.json', 'r') as fd:
            conf = json.load(fd)
        super().__init__(conf['hostname'], WiFi.DEVICE_TYPE)
        network.country(conf['country'])
        network.hostname(conf['hostname'])
        self._credentials = (conf['ssid'], conf['password'])
        self._wlan = network.WLAN(network.STA_IF)
        self._wlan.active(True)
        if not self._wlan.isconnected():
            # set led red for not connected
            self.report_event(Device.WF_SET_LED, (Led.LED_R, 1))
            self._connected = False # so we can spot a change
            self._wlan.connect(*self._credentials)
        else:
            self._connected = True
        self._check_timer = Timer(mode = Timer.PERIODIC, period = _REOPEN_TIME, callback = self._check_OK)

    def report_event(self, event, data):
        """Report an event

        This reports an event to the device. If the event is a WiFi connection event, it will """
        if self._tri_led is None:
            return super().report_event(event, data)
        else:
            # set the led here.
            self._tri_led.set(data[0], data[1])

    
    
    def isconnected(self):
        """Check if the WiFi is connected

        """
        return self._wlan.isconnected()
    
    def get_ssid(self):
        return(self._credentials[0])


    def _check_OK(self, _):
        """Check if the WiFi is connected

        This checks if the WiFi is connected. If it is newly connected, the LED is cleared.
        If it is not connected, the LED is set to red and the connection is attempted.
        If the connection is not established, the active state of the WiFi is toggled to force a reconnect.
        """
        if self._wlan.isconnected() and self._connected:
            return  # nothing to do
        if self._wlan.isconnected():
            # turn red led off
            self.report_event(Device.WF_SET_LED, (Led.LED_R, 0))
            self._connected = True
            return
        # not connected - do we need to report it
        if self._connected:
            # red led on
            self.report_event(Device.WF_SET_LED, (Led.LED_R, 1))
            self._connected = False
        if self._wlan.active(): # toggle active and await next tick
            self._wlan.active(False)
            return
        self._wlan.active(True)

        self._wlan.connect(*self._credentials)


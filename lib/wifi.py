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

import asyncio
from micropython import const
import network
from device import Device
from led_pio import NeoLed


import json


class WiFi(Device):
    """WiFi Connection
    
    This singleton class manages the WiFi Connection. It connects using the 
    credentials as held in the wifi configuration file.
    The connection is checked periodically and if the connection is lost, it will attempt to reconnect.
    The LED is set to red when not connected and cleared when connected.

    Attributes:
        DEVICE_TYPE: Wi-Fi device identifier.
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
        """
        if (WiFi._wi_fi) != None and (WiFi._wi_fi is not self):
            raise RuntimeError('only one instance allowed')
        self._led = NeoLed(NeoLed.COMMS_LED)
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
            self._led.set(NeoLed.LED_R)
            self._connected = False # so we can spot a change
            self._wlan.connect(*self._credentials)
        else:
            self._connected = True
        asyncio.create_task(self.check_OK())

 
    def isconnected(self):
        """Check if the WiFi is connected

        A wrapper for the standard MicroPython network class method.
        """
        return self._wlan.isconnected()
    
    def get_ssid(self):
        """Get the SSID
        
        returns:
            ssid
        """
        return(self._credentials[0])

    async def check_OK(self):
        """Check if the WiFi is connected

        This checks if the WiFi is connected. If it is newly connected, the LED is cleared.
        If it is not connected, the LED is set to red and the connection is attempted.
        If the connection is not established, the active state of the WiFi is toggled to force a reconnect.
        
        This runs forever as a task under asyncio
        """
        while True:
            await asyncio.sleep(5)  # 5 secs between checks
            if self._wlan.isconnected() and self._connected:
                continue  # nothing to do
            if self._wlan.isconnected():
                # turn red led off
                self._led.clear(NeoLed.LED_R)
                self._connected = True
                continue
            # not connected - do we need to report it
            if self._connected:
                # red led on
                self._led.set(NeoLed.LED_R)
                self._connected = False
            if self._wlan.active(): # toggle active and await next tick
                self._wlan.active(False)
                continue
            self._wlan.active(True)

            self._wlan.connect(*self._credentials)


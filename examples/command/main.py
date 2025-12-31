"""RP2 command station main.py

:author: Paul Redhead

This is the main entry point for the RP2 application running on the central command station. 
It starts the MQTT client and the DCC command and RailCom command response objects on the first core.
It also starts the screen and NeoString objects, and the DCC monitor on the second core.

All interrupt service routines and timer callbacks run on core 0. Asyncio is used for
co-operative multitasking on core 0.  No pre-emptive code
runs on core 1.

It is designed to run on the Raspberry Pi Pico or Arduino Nano RP2040 Connect.
It uses the micropython, machine, _thread, sys, network and asyncio modules.
It also uses the dcc_command, dcc_rc_ch2, neoled, screen, mqtt_cmd, mqtt, mqtt_client, dcc_mon, and device modules.
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
# python imports
import _thread, sys, network, asyncio

# micropython imports 
from micropython import const
from machine import Pin, ADC

# lib imports
from device import Device
from led_pio import NeoString
from screen import Screen

# DCC and RailCom imports
from dcc_command import DCCCommand
from dcc_rc_pio import RailComRead
from dcc_rc_ch2 import RComCmdRsp
from trk_mon import TrkMon

# MQTT imports
from mqtt_cmd import Power, Cab
from mqtt import Will
from mqtt_client import MQTTClient

from wifi import WiFi


def screen_splash():
    """create screen splash
    
    It's done here to avoid unnessesary imports in screen modules.
    """
    hostname = network.hostname()
    ssid = WiFi.get_instance().get_ssid()
    l0 = (0, '  DCC Cmnd Stn', 0)
    l1 = (1, '', 0)
    l2 = (2, f'{ssid} {hostname}', 0)
    l3 = (3, 'Standalone', 0)
    # override defaults.
    for _, dev in Device.get_items():
        if dev.get_type() == MQTTClient.DEVICE_TYPE:
            l3 = (3, f'MQTT {dev.get_broker()}', 0)
        elif dev.get_type() == RailComRead.GBL_DEVICE_TYPE:
            l1 = (1, 'RailCom Global', 0)
    return (l0, l1, l2, l3)


async def main():
    """Main function for the RP2 first core application.

    This function sets up the MQTT client and starts the main loop.
    It also sets up the DCC command and RailCom command response objects.
    The main loop reads the MQTT client and publishes the power state
    if it has changed.
    """

    DCC_STATE_MC = const(0) #DCC generation - First state machine on PIO 0
    RC2_STATE_MC = const(6) # RailCom Global detector state machine - 3rd on PIO 1

    dcc_pin = Pin(20, Pin.OUT) # common to both Arduino Nano Connect & Pico
    
    build = sys.implementation._build # get build description
    if build.find("PICO") > -1:
        # This includes Pico2 and W variants.
        # Detector pin allocations - Raspberry Pi Pico format
        # orientation pins are initiated but not specifically allocated
        c2_rx_pin = Pin(16, Pin.IN)
        _ = Pin(17, Pin.IN)
    elif build.find("NANO") > -1:
        # Detector pin allocations - Arduino Nano Connect format
        # orientation pins are initiated but not specifically allocated
        c2_rx_pin = Pin(15, Pin.IN)
        _ = Pin(16, Pin.IN)
    else:
        print (build, "invalid")

    DCCCommand(dcc_pin, sleep_pin, DCC_STATE_MC, enable_pin)

    RComCmdRsp(RC2_STATE_MC, c2_rx_pin, enable_pin)
    
    # list of MQTT Agents to be started.
    MQTT_LIST = [Power("track/power/set", MQTTClient.QOS1, "track/power/event"),
                    Will("track/state", MQTTClient.QOS1),
                    Cab("cab/+/+/#", MQTTClient.QOS1)]
  
    await MQTTClient.get_instance().run(MQTT_LIST)  # runs forever


def main1():
    """ Main function for the RP2 second core application.
    
    This function sets up the screen and NeoString objects, and starts the DCC monitor.
    It also enters a loop to read event reports and update the screen and NeoString accordingly.
    """
    fault_pin = Pin(21, Pin.IN, Pin.PULL_UP)  # low for true - DRV8874 Open Drain OP
    sense_pin = ADC(Pin(26)) # current sense input
    s = Screen().get_instance()
    trk_mon = TrkMon(sleep_pin, enable_pin, fault_pin, sense_pin)
    s.show_screen(screen_splash())
    
    
    while True:
        report = Device.get_event_report(False) # return immediately
        if report is not None:
            s.show_event(report)
        trk_mon.scan()


if __name__ == '__main__':
    # DRV8874 pin allocations - common to Pico & Arduino Nano Connect
    # sleep and enable are used by drivers in both cores
    # they are read only for everything but DCCCommand
    sleep_pin = Pin(19, Pin.OUT, value = 0)   # set sleep mode initially
    enable_pin = Pin(18, Pin.OUT, value = 1)
    _thread.start_new_thread(main1,())
    asyncio.run(main())

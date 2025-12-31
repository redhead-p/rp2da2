"""RP2 local detector main.py

:author: Paul Redhead

This is the main entry point for the RP2 application running a layout distributed pico. 
It starts the MQTT client and the RailCom block detector objects on the first core.
It also starts the screen and NeoString objects on the second core.

All interrupt service routines and timer callbacks run on core 0. Asyncio is used for
co-operative multitasking on core 0.  No pre-emptive code
runs on core 1.

It is designed to run on the Raspberry Pi Pico or Arduino Nano RP2040 Connect.
It uses the micropython, machine, _thread, sys, network and asyncio modules.
It also uses the dcc_rc_ch1, neoled, screen, mqtt_lcl, mqtt, mqtt_client, and device modules.
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
from micropython import const, alloc_emergency_exception_buf
from machine import Pin, ADC

# lib imports
from device import Device
from screen import Screen

# DCC and RailCom imports
from dcc_rc_ch1 import RComBlkDet
from dcc_rc_pio import RailComRead
from blk_mon import DCCBlkDet

# MQTT imports
from mqtt import Will
from mqtt_lcl import Block, Sensor
from mqtt_client import MQTTClient

from wifi import WiFi

alloc_emergency_exception_buf(100)


def screen_splash():
    """Create screen splash.
    
    It's done here to avoid unnessesary imports in screen modules.
    """
    hostname = network.hostname()
    ssid = WiFi.get_instance().get_ssid()
    t0 = (0, '  DCC ', 0)
    t1 = (1, '', 0)
    t2 = (2, f'{ssid} {hostname}', 0)
    t3 = (3, 'Standalone', 0)
    # override defaults.
    for _, dev in Device.get_items():
        if dev.get_type() == MQTTClient.DEVICE_TYPE:
            t3 = (3, f'MQTT {dev.get_broker()}', 0)
        elif dev.get_type() == RailComRead.LCL_DEVICE_TYPE:
            t1 = (1, 'RailCom Block', 0)
    return (t0, t1, t2, t3)


async def main():
    """Main function for the RP2 first core (core 0) application.

    Hardware allocations are defined for IO Pins and PIO State machines.
    This function sets up the MQTT client and starts the main loop.
    MQTT agents are set for the channel 1 block detectors
    The main loop polls the MQTT client
    """
    RC1A_STATE_MC = const(0) # RailCom Block A detector state machine number
    RC1B_STATE_MC = const(2) # RailCom Block B detector state machine number
                            
    RC1C_STATE_MC = const(6) # RailCom Block C detector state machine number

    build = sys.implementation._build # get build details
    if build.find("PICO") > -1:
        # Detector pin allocations - Raspberry Pi Pico format
        # orientation pins are initiated but not specifically allocated
        c1a_rx_pin = Pin(14, Pin.IN)
        _ = Pin(15, Pin.IN)
        c1b_rx_pin = Pin(16, Pin.IN)
        _ = Pin(17, Pin.IN)
        c1c_rx_pin = Pin(18, Pin.IN)
        _ = Pin(19, Pin.IN)
    else:
        print (build, "invalid")

    # List of MQTT agents to be started.
    mqtt_list = [Block(RComBlkDet('1011', RC1A_STATE_MC, c1a_rx_pin)),
                Block(RComBlkDet('1012', RC1B_STATE_MC, c1b_rx_pin)),
                Block(RComBlkDet('1013', RC1C_STATE_MC, c1c_rx_pin)),
                Sensor(DCCBlkDet('1011', ADC(26))),
                Sensor(DCCBlkDet('1012', ADC(27))),
                Sensor(DCCBlkDet('1013', ADC(28))),
                Will("track/state", MQTTClient.QOS1)]


    await MQTTClient.get_instance().run(mqtt_list)  # runs forever


def main1():
    """ Main function for the RP2 second core (core 1) application.
    
    This function sets up the screen.
    It also enters a loop to read event reports and update the screen and
    NeoString accordingly.
    """
    s = Screen().get_instance()

    s.show_screen(screen_splash())

    while True:
        report = Device.get_event_report() # wait until event received
        s.show_event(report)


if __name__ == '__main__':
    _thread.start_new_thread(main1,())
    asyncio.run(main())

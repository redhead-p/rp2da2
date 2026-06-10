"""RP2 local detector main.py

:author: Paul Redhead

This is the main entry point for the RP2 application running a layout distributed pico. 
It starts MQTT, RailCom and HeartBeat objects on the first core.
The second core is used to update the screen and leds.

All interrupt service routines and timer callbacks run on core 0.  No pre-emptive code
runs on core 1.

Python asyncio is used to provide cooperative multitasking on core 0. Asyncio is not
thread save and therefore cannot be used on core 1.

It is designed to run on the Raspberry Pi Pico2 W.
The Wi-Fi radio interface uses a PIO state machine. The Pico W doesn't have enough state
machines for concurrent Wi-Fi and quad RailCom.
It uses the micropython,  _thread, sys, network and asyncio libraries.
It also uses the dcc_rc_ch1, neoled, screen, mqtt_cmd, mqtt, mqtt_client, and device modules.
"""
"""       Copyright 2025, 2026  Paul Redhead

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
import _thread, asyncio

# micropython imports 
from micropython import alloc_emergency_exception_buf

# lib imports
from device import Device
from screen import Screen
from hw_conf import HwConfLcl
from led_pio import LedMan
import diagnostics

# DCC and RailCom imports
from dcc_rc_ch1 import RComBlkDet
from blk_mon import DCCBlkDet

# MQTT imports
from mqtt import Will
from mqtt_lcl import Block, Sensor
from mqtt_client import MQTTClient

alloc_emergency_exception_buf(100)

def build_config(blocks):
    """
    Build the configuration.

    Many objects that are part of the configuration are instantiated here. A
    list of mqtt agents that reference these objects is returned.

    Objects are instantiated in order. I.e. the first object gets the first set of
    hardware resources such as GPIO pins and so on.

    For track blocks both RailCom detectors and current based occupancy detectors are instantiated.
    
    args:
        blocks: List of block names in order

    returns:
        list of mqtt agents to be started
    """
    m_lst = []
    i = 0
    for blk_name in blocks:
        m_lst.append(Block(RComBlkDet(blk_name, i)))
        m_lst.append(Sensor(DCCBlkDet(blk_name, i)))
        i = i + 1
    m_lst.append(Will("track/state", MQTTClient.QOS1))
    return m_lst

async def main():
    """Main function for the RP2 first core (core 0) application.

    This function sets up the MQTT client and starts the main loop.
    MQTT agents are set for the channel 1 block detectors and conventional
    occupancy detectors.
    """
    diagnostics.HeartBeat.get_instance() # this will start the heart beat

    # this runs forever
    await MQTTClient.get_instance().run(build_config(('1011', '1012', '1013', '1014')))


def main1():
    """ Main function for the RP2 second core (core 1) application.
    
    This function sets up the screen.
    It also enters a loop to read event reports and update the screen and leds.
    """

    s = Screen().get_instance()
    l_man = LedMan.get_instance()
    while True:
        report = Device.get_event_report() # wait until event received
        l_man.update(report)
        s.show_event(report)
        diagnostics.log_event(report)

if __name__ == '__main__':
    HwConfLcl.get_instance() # load local board HW config
    _thread.start_new_thread(main1,())
    asyncio.run(main())

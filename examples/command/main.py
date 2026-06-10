"""RP2 command station main.py

:author: Paul Redhead

This is the main entry point for the RP2 application running on the central command station. 
It starts the MQTT client and the DCC command and RailCom command response objects on the first core.
It also starts the screen and NeoString objects, and the DCC monitor on the second core.

All interrupt service routines and timer callbacks run on core 0. Asyncio is used for
co-operative multitasking on core 0.  No pre-emptive code
runs on core 1.

It is designed to run on the Raspberry Pi Pico or Pico2.
It uses the micropython, machine, _thread, sys, network and asyncio modules.
It also uses the dcc_command, dcc_rc_ch2, led_pio, screen, mqtt_cmd, mqtt, mqtt_client, trk_mon, and device modules.
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
import _thread, sys, asyncio

# lib imports
from device import Device
from led_pio import ComsLed
from screen import Screen
from hw_conf import HwConfGbl
import diagnostics

# DCC and RailCom imports
from trk_mon import TrkMon

# MQTT imports
from mqtt_cmd import Power, Cab
from mqtt import Will
from mqtt_client import MQTTClient

async def main():
    """Main function for the RP2 first core application.

    It sets up the MQTT agents for track power and cab (throtle) usage. It starts the MQTT
    client and abdicates control to it. DCC command and RailCom command response objects
    are instantiated as required by MQTT agents.
    """
    diagnostics.HeartBeat.get_instance() # this will start the heart beat
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

    s = Screen.get_instance()
    trk_mon = TrkMon.get_instance()
    l = ComsLed.get_instance()
    
    while True:
        report = Device.get_event_report(False) # return immediately
        if report is not None:
            s.show_event(report)
            l.update(report[1], report[2])
            diagnostics.log_event(report)
        trk_mon.scan()


if __name__ == '__main__':
    HwConfGbl.get_instance() # load command station board HW config
    _thread.start_new_thread(main1,())
    asyncio.run(main())

"""RP2 layout device main.py

:author: Paul Redhead

This is the main entry point for the RP2 application running a layout distributed pico. 
It starts the MQTT client and the RailCom block detector objects on the first core.
It also starts the screen and NeoString objects on the second core.

It is designed to run on the Raspberry Pi Pico or Arduino Nano RP2040 Connect.
It uses the micropython, machine, and mqtt libraries.
It also uses the dcc_rc_ch1, neoled, screen, mqtt_cmd, mqtt, mqtt_client, and device modules.
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
import _thread, os, network

# micropython imports 
from micropython import const
from machine import Pin

# lib imports
from device import Device
from led import NeoString
from screen import Screen
from point import MPPoint, MPPointDriver

# DCC and RailCom imports
from dcc_rc_ch1 import RComBlkDet


# MQTT imports
from mqtt import Will, Block, RComBlkDet, TO
from mqtt_client import MQTTClient

from wifi import WiFi


def screen_splash():
    """Create screen splash.
    
    It's done here to avoid unnessesary imports in screen modules."""
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
        elif dev.get_type() == RComBlkDet.DEVICE_TYPE:
            t1 = (1, 'RailCom Block', 0)
    return (t0, t1, t2, t3)


def main():
    """Main function for the RP2 first core (core 0) application.

    This function sets up the MQTT client and starts the main loop.
    It also sets up the DCC command and RailCom command response objects.
    The main loop reads the MQTT client and publishes the power state if it has changed.
    """


    RC1A_STATE_MC = const(0) #RailCom Block A (channel 1) detector state machine number

    RC1B_STATE_MC = const(2) #RailCom Block B (channel 1) detector state machine number
    

    machine_descrip = os.uname().machine # get machine description
    if machine_descrip.find("Pico") > -1:
        # Detector pin allocations - Raspberry Pi Pico format
        # orientation pins are initiated but not specifically allocated
        c1a_rx_pin = Pin(14, Pin.IN)
        _ = Pin(15, Pin.IN)
        c1b_rx_pin = Pin(16, Pin.IN)
        _ = Pin(17, Pin.IN)
    elif machine_descrip.find("Nano") > -1:
        # Detector pin allocations - Arduino Nano  format
        # orientation pins are initiated but not specifically allocated
        c1a_rx_pin = Pin(0, Pin.IN)
        _ = Pin(1, Pin.IN)
        c1b_rx_pin = Pin(15, Pin.IN)
        _ = Pin(16, Pin.IN)
    else:
        print (machine_descrip, "invalid")


    # List of MQTT agents to be started.
    MQTT_LIST = [Block(RComBlkDet('1011', RC1A_STATE_MC, c1a_rx_pin)),
                Block(RComBlkDet('1012', RC1B_STATE_MC, c1b_rx_pin)),
                TO(MPPoint('1001', 0)),

                Will("track/state", MQTTClient.QoS1)]

    mc = MQTTClient.get_instance()
    mc.start(MQTT_LIST)
    while True:
        mc.read_poll()
        for agent in MQTT_LIST:
            agent.pub_check()


def main1():
    """ Main function for the RP2 second core (core 1) application.
    
    This function sets up the screen and NeoString objects.
    It also enters a loop to read event reports and update the screen and NeoString accordingly."""
    s = Screen().get_instance()
    #np = NeoString(Pin(22),2)
    s.show_screen(screen_splash())

    pd = MPPointDriver.get_instance()
    
    
    while True:
        report = Device.get_event_report() # wait until event received
        s.show_event(report)
        pd.set_to(report)
        #np.show_event(report)


if __name__ == '__main__':
    _thread.start_new_thread(main1,())
    main()

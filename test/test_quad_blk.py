""" Local Detector Board Block Occupancy Check

May be run as part of commissioning a newly constructed board as a check on
connection, soldering and functional integrity.

Requires device.py, diagnostics.py, hw_conf.py, blk_mon.py and led_pio.py

"""
"""        Copyright (C) 2026 Paul Redhead

        This program is free software: you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the Free Software Foundation, 
        either version 3 of the License, or (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
        See the GNU General Public License for more details.
        You should have received a copy of the GNU General Public License along with this program.
        If not, see <http://www.gnu.org/licenses/>.
"""

import asyncio, sys

import _thread

from device import Device
from blk_mon import DCCBlkDet
from hw_conf import HwConfLcl
from led_pio import LedMan
import diagnostics


async def main():
    """Main function for the RP2 first core (core 0) application.

    This function sets up the conventional
    occupancy detectors.
    """
    global s
    diagnostics.HeartBeat.get_instance() # this will start the heart beat

    s = [DCCBlkDet('t1', 0),
         DCCBlkDet('t2', 1),
         DCCBlkDet('t3', 2),
         DCCBlkDet('t4', 3)]
    while True:
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            break




def main1():
    """ Main function for the RP2 second core (core 1) application.
    
    It also enters a loop to read event reports and update leds.
    """

    l_man = LedMan.get_instance()
    while True:
        report = Device.get_event_report() # wait until event received
        l_man.update(report)
        diagnostics.log_event(report)

if __name__ == '__main__':
    HwConfLcl.get_instance()
    sys.argv.append('d') # enable logging
    _thread.start_new_thread(main1,())
    task = asyncio.run(main())
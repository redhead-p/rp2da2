"""Test harness for DCC Local Railcom channel 1 module.


This script is designed to run on a Raspberry Pi Pico or Arduino Nano Connect acting as a dual local detector.
It initializes the necessary pins and starts the RailCom channel 1 detectors.
It also includes a thread to display event reports and prints statistics about detection.

It uses the machine module for hardware interaction and the device module for event reporting.

"""
"""        Copyright (C) 2023, 2024, 2025, 2026 Paul Redhead

        This program is free software: you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the Free Software Foundation, 
        either version 3 of the License, or (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
        See the GNU General Public License for more details.
        You should have received a copy of the GNU General Public License along with this program.
        If not, see <http://www.gnu.org/licenses/>.
"""

import _thread, time, sys, asyncio

from micropython import alloc_emergency_exception_buf

from machine import Pin


from device import Device
from dcc_rc_ch1 import RComBlkDet
from dcc_rc_pio import RailComRead
from screen import Screen
from hw_conf import HwConfLcl
from led_pio import LedMan
import diagnostics

alloc_emergency_exception_buf(100)


time_stamp = time.ticks_ms()

ERR_CODE_DECODE = {
    RailComRead.ERR_WH:'W_HIGH',
    RailComRead.ERR_WL:'W_LOW',
    RailComRead.ERR_OE:'OVERRUN',
    RailComRead.ERR_CB:'CB_IN_DG',
    RailComRead.ERR_FE:'DG_INCOMP',
    RailComRead.ERR_ID:'UNRECOG_DG',
    RailComRead.ERR_PL:'PAYLD_ERR',
    RailComRead.ERR_RESP:'SYNC_ERR'}
    
def print_stats(reset = True):
    global time_stamp
    elapsed_time = time.ticks_diff(time.ticks_ms(), time_stamp)
    for block in (block_list):
        counts = block.get_error_counts()
        cb_count = block.get_cb_count()
        print(f'** Channel 1 {block.name} **')
        print(f"Msg. rate: {(cb_count) * 1000 / elapsed_time:.2f} per sec")
        for key, value in counts.items():
            print(f'{ERR_CODE_DECODE[key]}\t{value}')
        
        if cb_count > 0:
            print(f"err. rate: {(sum(counts.values())/cb_count):.0%}")
        if reset:
            block.reset_stats()
    time_stamp = time.ticks_ms()

user_sw = Pin(26, Pin.IN, Pin.PULL_UP) # user press button
async def lp():
    while True:
        try:
            await asyncio.sleep_ms(1)
            if not user_sw.value():
                # button press
                print_stats()
                print()
                while not user_sw():
                    await asyncio.sleep_ms(0)

        except KeyboardInterrupt:
            break


async def main():
    """Main function for the RP2 first core (core 0) application.

    This function sets up the RailCom local detectors.
    """
    global block_list
    diagnostics.HeartBeat.get_instance() # this will start the heart beat

    block_list = (RComBlkDet('Blk1', 0),
                RComBlkDet('Blk2', 1),
                RComBlkDet('Blk3', 2),
                RComBlkDet('Blk4', 3))
    
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
    s = Screen.get_instance()
    while True:
        report = Device.get_event_report() # wait
        l_man.update(report)
        s.show_event(report)
        diagnostics.log_event(report)

if __name__ == '__main__':
    HwConfLcl.get_instance()
    sys.argv.append('l') # enable logging
    _thread.start_new_thread(main1,())
    asyncio.create_task(lp())
    task = asyncio.run(main())
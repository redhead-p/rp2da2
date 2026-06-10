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
from led_pio import BlkLed
from screen import Screen


alloc_emergency_exception_buf(100)

if __name__ == '__main__':

    ERR_CODE_DECODE = {
        RailComRead.ERR_WH:'W_HIGH',
        RailComRead.ERR_WL:'W_LOW',
        RailComRead.ERR_OE:'OVERRUN',
        RailComRead.ERR_CB:'CB_IN_DG',
        RailComRead.ERR_FE:'DG_INCOMP',
        RailComRead.ERR_ID:'UNRECOG_DG',
        RailComRead.ERR_PL:'PAYLD_ERR',
        RailComRead.ERR_RESP:'SYNC_ERR'}


    build = sys.implementation._build # get build details
    
    if build.find("PICO2") > -1:
        # Detector pin allocations - Raspberry Pi Pico format
        c1a_rx_pin = 14
        c1b_rx_pin = 16
        c1c_rx_pin = 18
        c1d_rx_pin = 20
    elif build.find("PICO") > -1:
        # Detector pin allocations - Raspberry Pi Pico format
        c1a_rx_pin = 14
        c1b_rx_pin = 16
    elif build.find("NANO") > -1:
        # Detector pin allocations - Arduino Nano  format
        c1a_rx_pin = 0
        c1b_rx_pin = 15

        # second Dual reader - these pins are used for DRV8874
        # on command station

        c1c_rx_pin = 18
        c1d_rx_pin = 20
    else:
        print (build, "invalid")


    time_stamp = time.ticks_ms()

    block_list = (RComBlkDet('Blk1', 0, c1a_rx_pin, BlkLed(1), 27),
                RComBlkDet('Blk2', 2, c1b_rx_pin, BlkLed(2), 27),
                RComBlkDet('Blk3', 4, c1c_rx_pin, BlkLed(3), 27),
                RComBlkDet('Blk4', 6, c1d_rx_pin, BlkLed(4), 27))
    
    def main1():
        s = Screen()

        while True:
            report = Device.get_event_report(False)
            
            if report is not None:
                s.show_event(report)


            

    def print_stats(reset = True):
        global time_stamp
        elapsed_time = time.ticks_diff(time.ticks_ms(), time_stamp)  
        for block in (block_list):
            counts = block.get_error_counts()
            cb_count = block.get_cb_count()
            print(f'** Channel 1 {block.get_name()} **')
            print(f"Msg. rate: {(cb_count) * 1000 / elapsed_time:.2f} per sec")
            for key, value in counts.items():
                print(f'{ERR_CODE_DECODE[key]}\t{value}')
            
            if cb_count > 0:
                print(f"err. rate: {(sum(counts.values())/cb_count):.0%}")
            if reset:
                block.reset_stats()
        time_stamp = time.ticks_ms()

    async def lp():
        while True:
            try:
                await asyncio.sleep_ms(1)
            except KeyboardInterrupt:
                break



    _thread.start_new_thread(main1,())





if __name__ == '__main__':
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


    task = asyncio.run(lp())
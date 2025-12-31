"""Test harness for DCC Local Railcom channel 1 module.


This script is designed to run on a Raspberry Pi Pico or Arduino Nano Connect acting as a dual local detector.
It initializes the necessary pins and starts the RailCom channel 1 detectors.
It also includes a thread to display event reports and prints statistics about detection.

It uses the machine module for hardware interaction and the device module for event reporting.

"""



import _thread, time, sys

from micropython import alloc_emergency_exception_buf

from machine import Pin, ADC

from device import Device
from dcc_rc_ch1 import RComBlkDet
from dcc_rc_pio import RailComRead
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
        # orientation pins are initiated but not specifically allocated
        c1a_rx_pin = Pin(14, Pin.IN)
        _ = Pin(15, Pin.IN)
        c1b_rx_pin = Pin(16, Pin.IN)
        _ = Pin(17, Pin.IN)
        c1c_rx_pin = Pin(18, Pin.IN)
        _ = Pin(19, Pin.IN)
        c1d_rx_pin = Pin(20, Pin.IN)
        _ = Pin(21, Pin.IN)
    elif build.find("PICO") > -1:
        # Detector pin allocations - Raspberry Pi Pico format
        # orientation pins are initiated but not specifically allocated
        c1a_rx_pin = Pin(14, Pin.IN)
        _ = Pin(15, Pin.IN)
        c1b_rx_pin = Pin(16, Pin.IN)
        _ = Pin(17, Pin.IN)
    elif build.find("NANO") > -1:
        # Detector pin allocations - Arduino Nano  format
        # orientation pins are initiated but not specifically allocated
        c1a_rx_pin = Pin(0, Pin.IN)
        _ = Pin(1, Pin.IN)
        c1b_rx_pin = Pin(15, Pin.IN)
        _ = Pin(16, Pin.IN)

        # second Dual reader - these pins are used for DRV8874
        # on command station

        c1c_rx_pin = Pin(18, Pin.IN)
        _ = Pin(19, Pin.IN)
        c1d_rx_pin = Pin(20, Pin.IN)
        _ = Pin(21, Pin.IN)
    else:
        print (build, "invalid")


    time_stamp = time.ticks_ms()

    block_list = (RComBlkDet('t001', 0, c1a_rx_pin),
                RComBlkDet('t002', 2, c1b_rx_pin),
                RComBlkDet('t003', 6, c1c_rx_pin))
                #RComBlkDet('t004', 6, c1d_rx_pin))
    
    def main1():
        # bypass screen module to avoid pulling in MQTT & WiFi
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
            print(f'** Channel 1 block {block.get_name()} **')
            print(f"Call back rate: {(cb_count) * 1000 / elapsed_time:.2f} per sec")
            for key, value in counts.items():
                print(f'{ERR_CODE_DECODE[key]}\t{value}')
            
            if cb_count > 0:
                print(f"err. rate: {(sum(counts.values())/cb_count):.0%}")
            if reset:
                block.reset_stats()
        time_stamp = time.ticks_ms()

    _thread.start_new_thread(main1,())






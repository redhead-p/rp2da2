"""Test harness for DCC Railcom channel 1 module
This script is designed to run on a Raspberry Pi Pico or Arduino Nano Connect.
It initializes the necessary pins and starts the DCC command processing.
It also includes a thread to display event reports and prints statistics about command processing.

It uses the machine module for hardware interaction and the device module for event reporting."""



import _thread, time, os



from machine import Pin, ADC

from device import Device
from dcc_rc_ch1 import RComBlkDet
from screen import Screen
if __name__ == '__main__':

    # DRV8874 pin allocations - common to Pico & Arduino Nano Connect
    '''
    enable_pin = Pin(18, Pin.OUT, value = 1)
    sleep_pin = Pin(19, Pin.OUT, value = 0)   # set sleep mode initially
    dcc_pin = Pin(20, Pin.OUT)
    fault_pin = Pin(21, Pin.IN, Pin.PULL_UP)  # low for true - open drain OP on DRV8874
    sense_pin = ADC(Pin(26)) # current sense input
    '''

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


    time_stamp = time.ticks_ms()

    rc_ch1a = RComBlkDet('t001', 4, c1a_rx_pin)
    rc_ch1b = RComBlkDet('t002', 6, c1b_rx_pin)
    
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
        for block in (rc_ch1a, rc_ch1b):
            counts = block.get_error_counts()
            print(f'** Channel 1 block {block.get_name()} **')
            print("datagrams:",rc_ch1a.get_dg_list())
            print("errors   :", counts)
            #if total > 0:
            #    print(f"err. rate: {(sum(counts.values())/total):.0%}")
            if reset:
                block.reset_stats()
                block.reset_stats()

 
        if reset:
            time_stamp = time.ticks_ms()

    _thread.start_new_thread(main1,())






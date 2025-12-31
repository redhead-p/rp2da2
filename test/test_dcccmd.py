"""Test harness for DCC command module.

This script is designed to run on a Raspberry Pi Pico or Arduino Nano Connect acting as a command station
and global channel 2 detector.
It initializes the necessary pins and starts the DCC command processing.
It also includes a thread to display event reports and prints statistics about command processing.

It uses the machine module for hardware interaction and the device module for event reporting."""



import _thread, time, sys

from micropython import alloc_emergency_exception_buf

from machine import Pin, ADC

from device import Device
from dcc_command import DCCCommand
from dcc_cmd_util import CommandPacket
from dcc_rc_ch2 import RComCmdRsp
from dcc_rc_pio import RailComRead
from trk_mon import TrkMon
from screen import Screen
from led_pio import NeoString
if __name__ == '__main__':

    alloc_emergency_exception_buf(100)

    ERR_CODE_DECODE = {
        RailComRead.ERR_WH:'W_HIGH',
        RailComRead.ERR_WL:'W_LOW',
        RailComRead.ERR_OE:'OVERRUN',
        RailComRead.ERR_CB:'CB_IN_DG',
        RailComRead.ERR_FE:'DG_INCOMP',
        RailComRead.ERR_ID:'UNRECOG_DG',
        RailComRead.ERR_RESP:'SYNC_ERR'                
                }
    DYN_INFO_DECODE = {
        RComCmdRsp.DYN_REAL_SPEED:'SPEED',
        RComCmdRsp.DYN_TEMP:'TEMP',
        RComCmdRsp.DYN_DIRECTION:'DIRECTION',
        RComCmdRsp.DYN_RECEP_STATS:'RECEP_STATS',
        RComCmdRsp.DYN_TRACK_VOLT:'TRACK_VOLTS'

    }
    DYN_INFO_UNITS = {
        RComCmdRsp.DYN_REAL_SPEED:' km/h',
        RComCmdRsp.DYN_TEMP:' degC',
        RComCmdRsp.DYN_DIRECTION:'',
        RComCmdRsp.DYN_RECEP_STATS:'%',
        RComCmdRsp.DYN_TRACK_VOLT:' V'

    }
    # DRV8874 pin allocations - common to Pico & Arduino Nano Connect
    enable_pin = Pin(18, Pin.OUT, value = 1)
    sleep_pin = Pin(19, Pin.OUT, value = 0)   # set sleep mode initially
    dcc_pin = Pin(20, Pin.OUT)
    fault_pin = Pin(21, Pin.IN, Pin.PULL_UP)  # low for true - open drain OP on DRV8874
    sense_pin = ADC(Pin(26)) # current sense input

    build = sys.implementation._build # get build details

    if build.find("PICO") > -1:
        # Detector pin allocations - Raspberry Pi Pico format
        # orientation pins are initiated but not specifically allocated
        c2_rx_pin = Pin(16, Pin.IN)
        _ = Pin(17, Pin.IN)
    elif build.find("NANO") > -1:
        # Detector pin allocations - Arduino Nano  format
        # orientation pins are initiated but not specifically allocated

        c2_rx_pin = Pin(15, Pin.IN)
        _ = Pin(16, Pin.IN)
    else:
        print (build, "invalid")


    time_stamp = time.ticks_ms()
    
    rc_ch2 = RComCmdRsp(6, c2_rx_pin, enable_pin)
    
    dcc = DCCCommand(dcc_pin, sleep_pin, 0, enable_pin)

    def main1():
        s = Screen()
        s.show_screen(((3, "DCC Test", 0),))
        trk_mon = TrkMon(sleep_pin, enable_pin, fault_pin, sense_pin)

        while True:
            report = Device.get_event_report(False)
            
            if report is not None:
                s.show_event(report)

            trk_mon.scan()


    def print_stats(reset = True):
        global time_stamp
        elapsed_time = time.ticks_diff(time.ticks_ms(), time_stamp)  
        print("** Commands **")
        counts = CommandPacket.get_counts()
        total = sum(counts.values())
        print(f"Rate: {(total) * 1000 / elapsed_time:.2f} per sec")
        print('Command packets:',counts)
      
        counts = rc_ch2.get_error_counts()
        print("** Channel 2 **")
        print("datagrams:",rc_ch2.get_dg_list())
        for key, value in counts.items():
            print(f'{ERR_CODE_DECODE[key]}\t{value}')
        if total > 0:
            print(f"err. rate: {(sum(counts.values())/total):.0%}")
        #    print(f"ch2 time {rc_ch2.get_proc_time()//total}")
        if reset:
            rc_ch2.reset_stats()
            CommandPacket.reset_counts()
            time_stamp = time.ticks_ms()

    def print_dyn_info():
        print("** Dynamic Info **")
        for key in sorted(rc_ch2._dyn_info.keys()):
            addr, sub_index = key
            if sub_index == RComCmdRsp.DYN_TRACK_VOLT:
                value = (rc_ch2._dyn_info[key] / 10) + 5 # voltage in V
            elif sub_index == RComCmdRsp.DYN_DIRECTION:
                value = hex(rc_ch2._dyn_info[key])
            elif sub_index == RComCmdRsp.DYN_TEMP:
                value = rc_ch2._dyn_info[key] - 50
            else:
                value = rc_ch2._dyn_info[key]
            print(f'Address {addr}, {DYN_INFO_DECODE[sub_index]} {value}{DYN_INFO_UNITS[sub_index]}')

    _thread.start_new_thread(main1,())






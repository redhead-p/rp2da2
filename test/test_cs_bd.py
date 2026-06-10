""" Local Detector Board Initial Confidence Check

To be run as part of commissioning a newly constructed board as a check on
connection and soldering integrity rather than functionality.

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
from machine import Pin, I2C, ADC, Timer, unique_id, PWM
from neopixel import NeoPixel
from micropython import const
import sys, time

# PICO on board LED
led = Pin("LED", Pin.OUT)
# two neopixels in chain
np = NeoPixel(Pin(22), 2)


UNLIT = (0, 0, 0)
RED = (50, 0, 0)
GREEN = (0, 50, 0)
BLUE = (0, 0, 50)
WHITE = (40, 40, 40)
ORANGE = (40, 10, 0)


# pin used as inputs from detector 
rx_pin = Pin(16, Pin.IN)
# DRV8874 pins
drv_en = Pin(18, Pin.OUT, value = 0)     # not enabled
drv_nsleep = Pin(19, Pin.OUT, value = 0) # and asleep
drv_nfault = Pin(21, Pin.IN, pull = Pin.PULL_UP) # assert pull up
drv_cs =  ADC(0) #DRV8874 current sense
drv_phase = Pin(20, pull = None)

np.fill(UNLIT)
np.write()

DRV_CURRENT_RATIO = const(3300 / (0.45 * 2.49 * 65535))  #mA per unit ADC read

t1 = Timer() # LED Flasher

timer_test_num = 0
timer_step = 0
def timer_cb(t):
    global timer_test_num, timer_step
    if timer_test_num == 0:
        led.value(led.value() ^ 1)
    elif timer_test_num == 1:
        if timer_step == 0:
            np.fill(WHITE)
            timer_step = 1
        else:
            np.fill((UNLIT))
            timer_step = 0
        np.write()

def led_test():
    global timer_test_num
    timer_test_num = 0
    t1.init(mode = Timer.PERIODIC, freq = 1, callback = timer_cb)

def np_test():
    global timer_test_num
    timer_test_num = 1
    t1.init(mode = Timer.PERIODIC, freq = 1, callback = timer_cb)

def chk_proc():
    build = sys.implementation._build # get MicroPython build details
    print(build)
    print(f"Unique Id {unique_id().hex()}")

    if build.find("PICO") == -1:
        # not an RP Pico
        np.fill(RED)
        np.write()
        return
    np.fill((UNLIT))    
    if build.find("PICO2") == -1:
        # not Pico2 - must be Pico
        np[0] = GREEN
    else:
        np[0] = BLUE
    if build.find("_W") != -1:
        np[1] = BLUE
    np.write()

def scan_rx_pin(expect = 0):
    """Scan DRV8874 & RailCom detector Pins 

    Scan the GPIOs associated with the global RailCom detector output and DRV8874

    Global Detector RX is GPIO 16.

    DRV8874 fault is GPIO 21.
    """
    rx = rx_pin.value()
    print(rx_pin,":", rx, "Expected :", expect)
    np.fill(UNLIT)

    np[1] = GREEN if rx == expect else RED
    np.write()

def scan_i2c():
    """
    I2C sca and scl pins should be high due to pull ups.

    I2C0 scan returns decimal 60 (OLED).

    """
    sda = Pin(4, Pin.IN)
    scl = Pin(5, Pin.IN)
    print("sda",sda, sda.value())
    print("scl",scl, scl.value())
     # I2C0 scan should return decimal 60 (OLED)
    scan = I2C(0).scan()
    np.fill(UNLIT)
    if sda.value() == 0:
        np[0] = RED
    if scl.value() == 0:
        np[1] = RED
    if scl.value() == 0 or sda.value() == 0:
        # pull up missing
        np.write()
        return
    if 60 in scan:
        np[0] = GREEN
        np[1] = GREEN
    else:
        # orange orange
        np[0] = ORANGE
        np[1] = ORANGE
    np.write()
    print("I2C0 scan:", scan)

def test_drv8874(sleep = 0):
    """Test DRV8874 basics
    
    This checks the current sense analogue output from the DRV8874

    If sleep is true (0), fault will be false (1)

    If sleep is false (1) and no DC power to booster, fault will be true (0) - no power.

    If sleep is false (1) and DC power connected, fault will be false (1) - OK

    Args:
        sleep: 0 for True: 1 powered up - default - sleep

    """
    drv_en.value(1)
    drv_nsleep.value(sleep)
    time.sleep_ms(2)    # DRV8874 takes 1 ms to sleep or awake
    cs = drv_cs.read_u16()
    n_fault = drv_nfault.value()

    print("Enable", drv_en, drv_en.value(), "(1 for true)")
    print("Sleep", drv_nsleep, drv_nsleep.value(), "(0 for true)")
    print("Current Sense", cs, " => " , round(cs * DRV_CURRENT_RATIO,2), " mA")
    print("Fault", drv_nfault, n_fault)
    np.fill(UNLIT)
    np[1] = RED if n_fault == 0 else GREEN # 0 is fault true
    np[0] = (0, 0, min(255, cs // 32))
    np.write()

def test_detector(enable = 1):
    # check detector power
    np.fill(UNLIT)
    np.write()
    drv_en.value(enable)
    drv_nsleep.value(1)
    print("Control + C to terminate test")
    time.sleep_ms(2)    # DRV8874 takes 1 ms to sleep or awake
    # generate dcc '0' bits 200µs period 50% duty cycle
    pwm = PWM(drv_phase, freq = 5000, duty_u16 = 32768)
    try:
        while True:
            pass
    except KeyboardInterrupt:
        pass
    pwm.deinit()


tests = {
            0:("Flash Onboard LED", led_test,()),
            1:("Flash NeoPix", np_test,()),
            2:("Check processor", chk_proc,()),
            3:("Check Rx Pin Low", scan_rx_pin,(0,)),
            4:("Check I2C", scan_i2c,()),
            5:("Check DRV8874 : sleep = True", test_drv8874,(0,)),
            6:("Check DRV8874 : sleep = False", test_drv8874,(1,)),
            7:("Check detector power", test_detector, ())
        }


def do_test(tn = None):
    global test_num
    t1.deinit() # stop any flashing!
    led.value(1)
    if tn is not None:
        test_num = tn
    descrip, test_fn , param = tests[test_num]
    print(f"** {descrip} **")
    test_fn(*param)


if __name__ == '__main__':
    print()
    print("DCC Command Stn and RailCom Global Detector Commissioning Tests")
    print()
    nxt_tst = 0

    test_keys = sorted(tests.keys())
    # list tests
    for k in test_keys:
        print(k, tests[k][0])
    # stop when last test done
    while nxt_tst < len(test_keys):
        print()
        ip = input('>')
        print(ip)
        if ip:
            nxt_tst = int(ip)
        do_test(nxt_tst)
        nxt_tst += 1
        


    




""" Local Detector Board Initial Confidence Check

To be run as part of commissioning a newly constructed board as a check on
connection and soldering integrity rather than functionality.

"""

from machine import Pin, I2C, Timer, unique_id
from neopixel import NeoPixel
import time, sys
import micropython


# ADC1015 parameters to start read.
# 1st ADC is I2C address 72, 2nd 73
_ADC_CONF0 = b'\x95\xE3' # Single read, mux 1 (blk 1 or 3 differential), FSR 2048 mV, 3300 sps, comparator off
_ADC_CONF1 = b'\xA5\xE3' # as above mux 2 (blk 2 or 4 differential)
_ADC_CONF2 = b'\xB5\xE3' # as above mux 3 (differential but both on DCC-L so 0)
_ADC_CONF3 = b'\xE3\xE3' # mux 6 (single ended measurement of DCC-L wrt GND1), FSR 4096 mV
_ADC_CONF_ADD = 1
_adc_addr = {0:(72, _ADC_CONF0),
             1:(72, _ADC_CONF1),
             2:(73, _ADC_CONF0),
             3:(73, _ADC_CONF1),
             4:(72, _ADC_CONF2),
             5:(72, _ADC_CONF3),
             6:(73, _ADC_CONF2),
             7:(73, _ADC_CONF3)}

UNLIT = (0, 0, 0)
RED = (50, 0, 0)
GREEN = (0, 50, 0)
BLUE = (0, 0, 50)
WHITE = (40, 40, 40)
ORANGE = (40, 10, 0)


# pins used as rx inputs from detector
rx_pins = [Pin(x, Pin.IN) for x in (14, 16, 18, 20)]

or_pins = [Pin(x, Pin.IN) for x in (15, 17, 19, 21)]

ds_pin = Pin(21, Pin.IN)

# i2c pin numbers
i2c_pn = (4, 5),(6 ,7)

# PICO on board LED
led = Pin("LED", Pin.OUT)
# five neopixels in chain
np = NeoPixel(Pin(22), 5)
# user press button
sw = Pin(26, Pin.IN, Pin.PULL_UP)


np.fill(UNLIT)
np.write()

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



def scan_pins(pins):
    """Scan RailCom detector Pins 

    Scan the GPIOs associated with the local RailCom detector outputs.

    RX data pins have even numbers. Orientation indication pins are odd numbers,
    
    As it happens with no DCC power connected
    even numbered pins should be '0'
    and odd numbered pins '1'.

    With DDC power but no load pin inputs are reversed.
    I.e. even numbered pins '1' and
    odd numbered pins '0'

    With DCC power and a significant load on one of the blocks(e.g. loco fitted with
    decoder other than Zimo) and assuming the DCC cut out is not in force
    at the sample time:
    - the relevent even pin should be '0' and
    - the relevent odd pin depends on the DCC phase at the time of the sample.

    Take multiple samples to ensure both '0' and '1' readings are seen on odd numbered pin.
    """
    print("Control + C to stop test.")
    np.fill(UNLIT)
    try:
        while True:
            pin = iter(pins)
            for d in range(4):
                np[d] = GREEN if next(pin).value() == 1 else UNLIT
            np.write()
    except KeyboardInterrupt:
        pass

    for p in pins:
        print(p, p.value())



def scan_i2c(i):
    """
    I2C sca and scl pins should be high due to pull ups.
    
    With no DCC power connected
    I2C0 scan returns decimal 60 (OLED).
    I2C1 scan returns empty list [].
    
    With DDC power

    I2C0 scan returns decimal 60 (OLED).
    I2C1 scan returns decimal 72 & 73 (ADC).

    Args:
        i: I2C port number
    """
    """
    I2C sca and scl pins should be high due to pull ups.

    I2C0 scan returns decimal 60 (OLED).

    """
    sda = Pin(i2c_pn[i][0], Pin.IN)
    scl = Pin(i2c_pn[i][1], Pin.IN)
    print("sda",sda, sda.value())
    print("scl",scl, scl.value())
     # I2C0 scan should return decimal 60 (OLED) 
     # I2C1 scan should return decimal 72 & 73
    scan = I2C(i).scan()
    np.fill(RED)
    if sda.value() == 1:
        np[0] = GREEN
    if scl.value() == 1:
        np[1] = GREEN

    if 60 in scan:
        np[2] = BLUE
    if 72 in scan:
        np[3] = BLUE
    if 73 in scan:
        np[4] = BLUE    
 
    np.write()
    print(f"I2C{i} scan: {scan}")



def test_sw2():
    """check user button 

        Test the user button (SW2) and NeoPixel chain.
        Pico on board LED should show opposite of last Neopixel.
        If on board LED toggles with button, button is OK.
        If Neopixel doesn't toggle but LED does, Neopixel chain problem.

        Ctrl + C to exit.
    """
    print("Control + C to stop test.")
    np.fill(UNLIT)
    try:
        while True:
            swv = sw.value()
            led.value(swv ^ 1)
            #np.__setitem__(np.__len__() - 1, (swv * 20,0,0))
            np[-1] = (swv * 20,0,0)
            np.write()
    except KeyboardInterrupt:
        print("SW 2 Test Exit")
        np.fill(UNLIT)
        np.write()
        led.value(0)

def test_DCC_sense():
    np.fill(UNLIT)
    np.write()
    count = 0
    def disp(c):
        np.fill(UNLIT)
        np[c % 5] = BLUE
        np.write()


    def _sense_isr(pin):
        nonlocal count
        if pin.value() == 0:
            # pin reverted back to DCC on - too short for cutout
            return
        # assumed cut out
        count += 1
        micropython.schedule(disp, count)


    sense_pin = Pin(27, Pin.IN)
    sense_pin.irq(_sense_isr, Pin.IRQ_RISING, hard = True)
    time.sleep(10)
    sense_pin.irq(None)
    print("Cutout frequency:", count  / 10, "per sec.")





def test_adc():
    """Test ADC conversion
    
    This tests the raw DCC side ADC sampling as used for block occupancy.
    Nominally this is a differential reading of the voltage across the load sense
    1.8 ohm resistor.

    The sample is not timed wrt the DCC phasing or cut out and
    for a given load may vary in value and sign.
    Due to offset bias in the analogue circuitry
    the zero load reading will usually be non zero. 
    These factors are allowed for by taking multiple reads and filtering in the main application but not here!
    
    The no load reading should be in the range ±25 and for a given block will be more or less constant.
    The load for a 10K resistor in the range ±(50 - 150) after allowing for offset but lower values may occasionally be seen.
    The load for a decoder > ±1000 but this will depend on the decoder's quiescent current. Lower values may occasionally be seen.

    Readings 1 to 4 are block differential readings wrt DCC-L.
    5 and 7 are differential readings of DCC-L against itself. Should always be 0.
    6 and 8 are single ended readings of DCC-L wrt GND1. Should be c.1250 corresponding to 5/2 V.
    """

    def _adc2int(adc_res):
        # this is a 12 bit signed (2's comp) value but left aligned.  L.S 4 bits always 0
        value = (adc_res[0] << 4) + (adc_res[1] >> 4)
        if (adc_res[0] & 0x80) != 0:
            value = ((~value & 0x0fff) + 1) * -1
        return(value)
   
    for adc in sorted(_adc_addr.keys()):
        i2c_addr, conf = _adc_addr[adc]
        try:
            I2C(1).writeto_mem(i2c_addr,_ADC_CONF_ADD,conf) # start read
            while True:
                res = I2C(1).readfrom_mem(i2c_addr,_ADC_CONF_ADD, 2)
                if (res[0] & 0x80) != 0:
                    break   # we have a result
            value = _adc2int(I2C(1).readfrom_mem(i2c_addr, 0, 2))
            print(adc + 1, value)
                
        except OSError:
            # i2c error - no track power most likely
            print("Is DCC power on?")
            return

tests = {
            0:("Flash Onboard LED", led_test,()),
            1:("Flash NeoPix", np_test,()),
            2:("Check processor", chk_proc,()),
            3:("Check User Switch", test_sw2,()),
            4:("Check I2C 0", scan_i2c,(0,)),
            5:("Check I2C 1", scan_i2c,(1,)),
            6:("Check rx pins", scan_pins, (rx_pins,)),
            7:("Check or pins", scan_pins, (or_pins,)),
            8:("DCC Sense", test_DCC_sense,())
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
    print("RailCom Quad Local Detector Commissioning Tests")
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
        

# rp2da2

Model Railway Distributed Automation for RP2 (and other MicropPython MCUs).

---

## Hardware and Environment

The primary target Micro Controller Units for this project are Raspberry Pi RP2
based and run MicroPython V1.26 or later. Testing has principly taken place on
Pico, Pico W and Arduino Nano RP2040 Connect platforms. Elements of the application
may run on other MicroPython capabable platforms with no, or minor modifications.
DCC and RailCom components use the RP2 Programmable IO peripheral so must be run
on an RP2 based MCU. RP2350 based MCUs such as the Pico 2 W should be acceptable
but this is as yet untested.

A booster is required to convert the DCC signal into a form suitable for
suppling power directly to track. The reference booster is the Texas
Instruments DRV8874 mounted on a Pololu header. This may deliver up to 2.9 A
instantaniously but is only rated for 2.1 A continuous load. You will also
need a suitable DC power supply.

RailCom detectors have been specifically designed for this project with circuit
schematics and PCB designs for both global and local detectors. The PCB designs
and applications have been designed around a standard set of GPIO pin
allocations. The following table shows pin allocations for a local detector.

| GPIO Pin | Pico / Pico W |Arduino Nano|
| --- | --- | --- |
|0| - | RailCom ch 1 (a) rx |
|1| - | RailCom ch 1 (a) orientation|
|4| OLED I2C0:sda | - |
|5| OLED I2C0:scl |- |
|12| - | OLED I2C0:sda |
|13| - | OLED I2C0:scl |
|14|RailCom ch 1 (a) rx | - |
|15|RailCom ch 1 (a) orientation|RailCom ch 1 (b)|
|16|RailCom ch 1 (b)|RailCom ch 1 (b) orientation|
|17|RailCom ch 1 (b) orientation| - |
|18|RailCom ch 1 (c) rx|RailCom ch 1 (c) rx|
|19|RailCom ch 1 (c) orientation|RailCom ch 1 (c) orientation|
|20|RailCom ch 1 (d) rx|RailCom ch 1 (d) rx|
|21|RailCom ch 1 (d) orientation|RailCom ch 1 (d) orientation|
|22|NeoPixel chain|NeoPixel chain|

When configured as a command station one channel 2 global detector is
available. Pin allocations for the command station are as follows.

|GPIO Pin (Pico & Nano)| Function|
|---|---|
|4| OLED I2C0:sda (Pico)|
|5| OLED I2C0:scl (Pico)|
|12|OLED I2C0:sda (Nano)|
|13| OLED I2C0:scl (Nano)|
|15| RailCom Ch 2 rx (Nano)|
|16| RailCom Ch 2 rx (Pico)|
|18|DRV8874 EN|
|19|DRV8874 nSleep|
|20|DRV8874 PH|
|21|DRV8874 nFault|
|26|DRV8874 Current Sense|
|Ground|DRV8874 iMode|
|Ground|DRV8874 pMode|
|NC|DRV8874 Vref|
|22|NeoPixel chain|

## Software Modules

### Utility & UI

**device** - This provides the Device class, a base class for hardware device
drivers and similar objects.

**oled0_91** - Module for 0.91 inch OLED on i2c

**led** - Module to drive ws2812 LEDs or similar.  A string of 2 LEDs is supported.
The first LED displays the backend communications state, the second
displays the command station track status.

**screen** - This is the screen application module. It specifies the Screen class.

### Communications

**mqtt_client** - This provides a simple MQTT client.

**mqtt\*** - Other MQTT modules provide interfaces for MQTT devices and agents.
These may be used with JMRI but JMRI MQTT specifications will need to be
changed from the default. Initially we support cabs, power and blocks.
Blocks have combined occupancy sensor and reporter.

**wifi** - This acts as wrapper for the standard MicroPython network/Wi-Fi functions.

### DCC and RailCom

These modules are dependent on RP2 series processor programable input/output peripherals (PIO)
for DCC command serialisation and RailCom response processing.

**dcc_command** - This module provides high level APIs. It and associated modules contain
the functions and classes for DCC command station.

**dcc_cmd_util** - This module contains classes for DCC command objects.

**dcc_cmd_pio** - This module contains the class and functions for low level
DCC Command Serialisation for use with RailCom detection.

**dcc_rc_ch1** - This module contains the functions and classes for DCC RailCom
block detection on Channel 1.

**dcc_rc_ch2** - This module contains the functions and classes for DCC RailCom
command station mobile responses on Channel 2.

**dcc_rc_pio**  - This module contains the functions and classes for low level
RailCom datagram reading. It's applicable for block occupancy detection on
Channel 1 and central dcc command decoder responses on Channel 2.

**trk_mon** - This module monitors the booster and track status by looking at the DRV8874
enable, fault and current sense pins.

---

## Configuration

Configuration files hold information required at runtime.  The files use the JSON format.
They are held in the repository's conf directory. They must be copied to a top level directory on the
target machine called conf. The configuration files in the repository should be taken as examples.
They need to be modified outside the repository to reflect local requirements. The Thonny editor
may be used to update them as required once they have been copied to the target machine.

### Wi-Fi

The config file specifies:

- Network country code
- SSID - your Wi-Fi network name
- password - the network password
- host name - the name to be used by local machine. This needs to be changed
from the MicroPython default to avoid duplicates.

### MQTT

The config file specifies:

- the MQTT broker's host name
- the local machine client ID.  The client id is required as mosquitto does not permit anonymous access.
- port - the MQTT port number. By default this is set to 1883 and this setting may be ommitted.

---

## Installation

### General

Copy the python (.py) files from the lib and rp2dcc directories to the Pico using Thonny or similar.
Don’t replicate the repository directory structure, just copy to the top level or if you want to be tidier
you can copy the .py files to the lib directory. Don’t bother with the \_\_init\_\_.py  files.
These are purely documentary at the moment.
Also ignore the test directory.

The screen driver will object if it can’t find the OLED on the i2c bus.
Most 0.91" OLEDs include i2c pull-ups so these should not be needed.

### Command Station

The main.py in the examples/command directory is a command station version. It provides MQTT connectivity
allowing the command station to be controlled from JMRI or similar.
Copy this main.py from the command directory to the top level directory on the target device.
Alternatively there is a test harness test_dcccmd.py in the test directory.
This may be run using Thonny. Load this into the Thonny editor window and ‘Run current script’
(green play button). It will auto-detect whether on a RP Pico or
Arduino Nano RP2040 Connect and allocate the detector pins accordingly.
It creates the DCCCommand object (named dcc).

If OK you will get an invitation to type at the REPL, but the program will still be
running in the background. The OLED display shows a ’splash’.

You can enter DCC API commands at the REPL preceded by
'dcc.'. E.g.:

```py
>>> dcc.power(1)
```

### Block Detector

The main.py scripts in the dual\_ and quad\_ local_detect directories are the block detector versions. The version in the dual directory monitors two blocks, and that in the quad directory four.
They provide MQTT connectivity
allowing the block detector to report to JMRI or similar.
Copy the main.py from the dual or quad directory to the top level directory on the target device.

Alternatively there is a test harness test_dccrc1.py in the test directory.
This may be run using Thonny. Load this into the Thonny editor window and ‘Run current script’
(green play button). It will auto-detect whether on a RP Pico or
Arduino Nano RP2040 Connect and allocate the detector pins accordingly.
It creates the channel 1 block detector objects for the blocks.

If OK you will get an invitation to type at the REPL, but the program will still be running
in the background. The OLED display shows a ’splash’.
Block occupancy details will be displayed on the OLED screen.

---

## DCC API

### Module dcc_command

---
class **DCCCommand** *(DCC_pn, sleep_pn, gen_sm_num, enable_pn)*

Parameters

- *DCC_pn* Pin number allocated for DCC output.

- *sleep_pn* Pin number allocated to the booster for powering the track

- *gen_sm_num* PIO state machine number to be used for DCC Generation

- *enable_pn* Pin number to enable the DRV8874.

---

method **power** *(p=None)*

DCC Power On/Off

Start and stop command packet transmission scheduling.

Changing the power state will cause the new power state available flag to be set.

Parameters

- *p* 1 for power on, 0 for power off, None for get power status

Returns

- power status as held by the DCC generator.

---

method **read_cv** *(address, cv_num)*

This initiates reading a CV using Programming on Main in conjunction with RailCom.
The command is validated and the read request scheduled for action. The addressed decoder must be
active and the command will be rejected by the command generator class this is not true.

The CV value will be displayed on the OLED.

Parameters

- *address*

- *cv_num* cv number as entered - users count from 1, DCC counts from 0!

---

method **write_cv** *(address, cv_num, new_val)*

This initiates writing a CV using Programming on Main in conjunction with RailCom.

The command is validated and the write request scheduled for action. The addressed
decoder must be active and the command will be rejected by the command generator class
this is not true.

The updated CV value will be displayed on the OLED if the write is successful.

Parameters

- *address*

- *cv_num* cv number as entered - users count from 1, DCC counts from 0!

- *new_val* the new value for the CV

---

method **set_fg1** *(address, f_num, state)*

Set Function Group 1

This sets or clears a function in group 1. The forward light is usually function number 0.

See NMRA S-9.2.1 Section 2.3.4

Parameters

- *address* the address of the decoder - may be short or long

- *f_num* function number to set or clear

- *state* 1 for set, 0 for clear

Returns

- True if validation is passed and the packet is scheduled for transmission. False if validation fails.

---

method **set_speed** *(address, dir, speed)*

Set Speed.

This sets the direction and speed. Direction may be forward or reverse.

The packet generated will be for a 128 step speed setting and decoders must be configured for
28/128 speed steps.

See NMRA S-9.2.1 Section 2.3.2.1

Parameters

- *address* the address of the decoder - may be short or long

- *direction* 1 for forward, -1 for reverse

- *speed* the speed to be set - range 0 to 127

Returns

- True if validation is passed and the packet is scheduled for transmission. False if validation fails.

---

method **wait_for_flag** *()*

Wait for the new state available flag.

The new state available flag is an instance of the asyncio.ThreadSafeFlag class
and when set, it indicates that the power state has changed. This method waits
for the flag to be set.
It must be called from a coroutine.

---

Available constants are:

```py
# Forward direction
FWD = const(1)

# Reverse Direction
REV = const(-1)

# Power Off
OFF = const(0)

# Power On
ON = const(1)
```

---

### Module dcc_rc_ch1

---

class **RComBlkDet** *(blk_name, rc_sm_num, rx_pin, enable_pin = None)*

Parameters

- *blk_name* the name of the block
- *rc_sm_num*  the first state machine number.
- *enable_pn* the pin as used by the DCC generator to assert the RailCom cutout (optional).

---

method **wait_for_flag** *()*

Wait for the new block state available flag.

The new state available flag is an instance of the asyncio.ThreadSafeFlag class
and when set, it indicates that the block detection state state has changed.
This method waits for the flag to be set.
It must be called from a coroutine.

---

method **get_block_state** *()*

Get the current block state

This returns the current block state. The block state is a tuple of the block
status and any RailCom information available. The block status may be:

- *Device.UNKNOWN* the block state is unknown
- *Device.EMPTY* the block is empty
- *Device.BLK_OCC* the block is occupied, but no RailCom Channel 1 information is available
- *Device.BLK_CH1* the block is occupied and RailCom Channel 1 information is available

RailCom information, if available, is a tuple:

- *address type* 's', 'l' or 'c' for short, long or consist
- *address* as an integer number
- *orientation* 1 or -1

---

method **get_error_counts** *()*

Get Error Counts

Counts of errors are kept. Broadly errors are communication errors or content errors. Content errors
may be caused by faulty decoders, but typically are the result of undetected communicaton errors.

Communication errors are:

- Overrun error (missing stop bit)
- Hamming Weighting high or low (not 4)

See code for other errors.

---

method **get_cb_count** *()*

Get Read Count

The number of calls to the read routine. I.e the number of times
that data has been received during a channel 1 window.

---

method **reset_stats** *()*

Reset Statistics

Reset error counts etc.

---

### DCC Diagnostics

---

function **print_stats** *(reset = True)*

This prints diagnostic information on DCC commands
and RailCom. By default the diagnostics are cleared after being printed.
Available in both test_dcccmd and dccrc1 modules.

---

function **print_dyn_info** *()*

This prints dynamic information received from decoders (datagram id 7).
Available in test_dcccmd module.

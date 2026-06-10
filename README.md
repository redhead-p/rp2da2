# rp2da2

Model Railway Distributed Automation for RP2 (and other MicropPython MCUs).

---

## Hardware and Environment

The primary target Micro Controller Units for this project are Raspberry Pi RP2
based and run MicroPython V1.26 or later. Testing has principly taken place on
Pico, Pico W, Pico 2W and Arduino Nano RP2040 Connect platforms.
DCC and RailCom components use the RP2 Programmable IO peripheral so must be run
on an RP2040 or RP2350 based MCU.
Other application components
may run on other MicroPython capabable platforms with no, or minor modifications.

Primary components are:

- a command station with integrated booster/RailCom cutout and global RailCom detector
- a local RailCom detector module with up to four detectors and current based occupancy detection.

A booster is required to convert the DCC signal into a form suitable for
suppling power directly to track. The reference booster is the Texas
Instruments DRV8874 mounted on a Pololu header. This also acts as the RailCom cutout. This may deliver up to 2.9 A
instantaniously but is only rated for 2.1 A continuous load. You will also
need a suitable DC power supply.

RailCom detectors have been specifically designed for this project with circuit
schematics and PCB designs for both command station and local detectors. The PCB designs
and applications have been designed around a standard set of GPIO pin
allocations. The local RailCom detector also provides a block occupancy indication using
conventional current flow detection. This triggers at a nominal 1 mA enabling detection of 10 kΩ wheel set resistors.
SPI1 and other GPIO pins not currently used by the application suite
may be exposed PCB on headers.

### GPIO Pins, I2C & SPI

On the command station one global detector is
available for the receipt of Channel 2 datagrams. Pin allocations for a Pico based command station are as follows.
Pin allocations on other platforms may differ.

|GPIO Pin (Pico & Nano)|Function|
|---|---|
|4|OLED I2C0:sda|
|5|OLED I2C0:scl|
|16|RailCom Ch 2 rx|
|18|DRV8874 EN|
|19|DRV8874 nSleep|
|20|DRV8874 PH|
|21|DRV8874 nFault|
|22|NeoPixel chain (2 LEDs)|
|26|DRV8874 Current Sense|
|Ground|DRV8874 iMode|
|Ground|DRV8874 pMode|
|NC|DRV8874 Vref|

The following table shows pin allocations for a four block local detector on a Pico series
platform. Pin allocations on other platforms may differ. Other platforms may be able to
support additional local detectors.

I2C0, I2C1 and SPI1 pin assignments follow the MicroPython default pin assignments for
these peripherals.

SPI1 may be wired to a PCB header for off board connection.

I2C1 is used to support conventional current based detector functions.
It may be wired to a PCB header for off board connection too.

|GPIO Pin|Pico / Pico W|
|---|---|
|4|OLED I2C0:sda|
|5|OLED I2C0:scl|
|6|I2C1:sda|
|7|I2C1:scl|
|8|SPI1 MISO|
|9|SPI1 CS(primary)|
|10|SPI1 SCK|
|11|SPI1 MOSI|
|12|SPI1 additional GPIO (e.g. interrupt)|
|13|SPI1 CS(alternative)|
|14|RailCom ch 1 (a) rx|
|15|RailCom ch 1 (a) orientation|
|16|RailCom ch 1 (b) rx|
|17|RailCom ch 1 (b) orientation|
|18|RailCom ch 1 (c) rx|
|19|RailCom ch 1 (c) orientation|
|20|RailCom ch 1 (d) rx|
|21|RailCom ch 1 (d) orientation|
|22|NeoPixel chain (5 LEDs)|
|26|User press button|
|27|RailCom cutout detect|

### Programmable Input/Output & State Machines

The DCC and RailCom components make extensive use of the RP2 Programmable
Input/Output (PIO) peripherals. Each PIO peripheral has four State Machines.
On the Pico W and Pico2 W use of the radio module also requires use of a PIO
State Machine and a State Machine may also be used to drive a NeoPixel chain.
The RP2040 has 2 PIO peripherals and the RP2350 has 3.  MicroPython numbers
the State Machines on these as 0 to 7 and 0 to 11 respectively.

Note that the tables show the default radio state
machines as grabbed if available by the MicroPython
Wi-Fi module/RP SDK library.
The MicroPython application code leaves these
free for the radio rather than specifically
allocating them.

#### Command Station/Global Detector

|State Machine|Function|
|---|---|
|0|DCC generation|
|1 - 3|Not available. DCC generation uses virtually all PIO 0 memory|
|4|Radio on Pico W|
|5|NeoPixel on Pico / Pico W|
|6|RailCom Channel 2 timing|
|7|RailCom Channel 2 RX|
|8|Radio on Pico2 W|
|9|NeoPixel on Pico2 / Pico2 W|

#### Local Detector

|State Machine|Function|
|---|---|
|0|Block A RailCom Channel 1 timing|
|1|Block A RailCom RX|
|2|Block B RailCom Channel 1 timing|
|3|Block B RailCom RX|
|4|Block C RailCom Channel 1 timing|
|5|Block C RailCom RX|
|6|Block D RailCom Channel 1 timing|
|7|Block D RailCom RX|
|8|Radio on Pico2 W|
|9|NeoPixel on Pico2 / Pico2 W|

## Software Modules

### Utility & UI

**device** - This provides the Device class, a base class for hardware device
drivers and similar objects.

**diagnostics** - This provides the singleton HeartBeat class and the logger function.

**hw_conf** - This configures the Pico hardware.

**oled0_91** - Module for 0.91 inch OLED on i2c0

**led_pio** - Module to drive ws2812 LEDs or similar.  A string of up to five LEDs is supported.
The first LED displays the backend communications state. Additional LEDs display the
command station track status or local block status as appropriate.

**screen** - This is the screen application module. It specifies the Screen class.

### Communications

**mqtt_client** - This provides a simple MQTT client. Use of MQTT requires an MQTT broker. E.g Mosquitto. There are ports
of this for Windows, MAC/OS, and Linux (e.g. Ubuntu, Raspberry Pi OS).

**mqtt\*** - Other MQTT modules provide interfaces for MQTT devices and agents.
These may be used with JMRI but JMRI MQTT specifications will need to be
changed from the default. Initially we support cabs, power and blocks.
Blocks include occupancy sensor and RailCom reporter.

**wifi** - This acts as wrapper for the standard MicroPython network/Wi-Fi functions.

### DCC and RailCom

These modules are dependent on RP2 series processor programable input/output peripherals (PIO)
for DCC command serialisation and RailCom response processing.

#### Command Station Modules

**dcc_command** - This module provides high level APIs. It and associated modules contain
the functions and classes for DCC command station.

**dcc_cmd_util** - This module contains classes for DCC command objects.

**dcc_cmd_pio** - This module contains the class and functions for low level
DCC Command Serialisation for use with RailCom detection.

**dcc_rc_ch2** - This module contains the functions and classes for DCC RailCom
command station global detector mobile responses on Channel 2.

**trk_mon** - This module monitors the booster and track status by looking at the DRV8874
sleep, enable, fault and current sense pins.

#### Local RailCom Detector Modules

**dcc_rc_ch1** - This module contains the functions and classes for DCC RailCom
block detection on Channel 1.

**blk_mon** - This module contains classes for block occupancy detection based on current
consumption. It works in parallel with the RailCom Channel 1 detector.

#### Common Module

**dcc_rc_pio**  - This module contains the functions and classes for low level
RailCom datagram reading. It's applicable for block occupancy detection on
Channel 1 and central dcc command decoder responses on Channel 2.

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

```json
{"country": "myCountry", "password": "myPassword", "ssid": "mySSID", "hostname":"myHostName"}
```

### MQTT

***Pico Configuration***

The config file specifies:

- the MQTT broker's host name
- the local machine client ID.  The client id is required as by default Mosquitto will not permit access without it. However if not specified here the client id will be set to the network host name.
- port - the MQTT port number. By default this is set to 1883 and this setting may be ommitted.

```json
{"broker": "myBroker", "clientId": "myClientName", "port": 1883}
```

On the command station the MQTT connection supports track power and cabs.
On the local detector the MQTT connection supports sensor updates and reporters.
The MQTT connection may be used to communicate with JMRI.
Generally topics match those used by JMRI but some modifications are required to JMRI defaults
as configured on the MQTT connections settings.

***Mosquitto Configuration***

The Mosquitto configuration file is held in mosquitto.conf. The location of the file is OS dependent.
For Raspberry Pi OS it's

```text
/etc/mosquitto/mosquitto.conf
```

A couple of lines may need to be added.

```text
allow_anonymous true

listener 1883
```

Note that connections to Mosquitto will not be authenticated. Do not do this unless inward connections to your network are blocked (or you don't mind aliens hacking your model railway).

***JMRI MQTT Configuration***

  Check 'Additional Connection Settings' under
Preferences->Connections for the MQTT connection to access the JMRI MQTT configuration.

|Setting|Value|
|---|---|
|Sensor send topic:|track/sensor/{0}/set|
|Sensor receive topic:|track/sensor/{0}/event|
|Power send topic:|track/power/set|
|Power receive topic:|track/power/event|

---

## Software Installation

### General

Copy the python (.py) files from the lib and rp2dcc directories to the Pico using Thonny or similar.
Don’t replicate the repository directory structure. Copy the files from both directories to the
lib directory at the Pico files system top level.
Note that MicroPython will only search the top level directory and the lib directory for
*.py files.
Don’t bother with the \_\_init\_\_.py  files.
These are purely documentary at the moment.
Also ignore the test directory.

The screen driver will object if it can’t find the OLED on the i2c bus.
Most 0.91" OLEDs include i2c pull-ups so these should not be needed.

Copy the files from the conf directory to a directory on the Pico named conf.  Edit the configuration files
**after copying**.

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

The main.py scripts in the dual\_, and quad\_ local_detect directories are the block detector versions. They
monitor two and four blocks respectively.

They provide MQTT connectivity
allowing the block detector to report to JMRI or similar.
Copy the main.py from the dual or quad directory to the top level directory on the target device.

Alternatively there are test harnesses in the test directory.

***test_dccrc1.py*** runs the local RailCom detectors.

***test_quad_blk.py*** runs the current based occupancy Train detectors.

Both may be run using Thonny. Load the program into the Thonny editor window and ‘Run current script’
(green play button). The program will auto-detect whether on a RP Pico or
Arduino Nano RP2040 Connect and allocate the detector pins accordingly.
It creates the channel 1 block detector objects or current based detector for the blocks.

The program will run forever.

Block occupancy details will be displayed on the OLED screen. Press the user button to see RailCom stats.

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
for the flag to be set. When called from another asynchio thread
that thread will wait pending the setting of the flag.
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

class **RComBlkDet** *(blk_name, rc_sm_num, rx_pin, led, dcc_pin)*

Parameters

- *blk_name* the name of the block
- *rc_sm_num*  the first state machine number
- *rx_pin* the RailCom local detector rx data pin
- *led* the led number on the led string associated with the block
- *dcc_pin* the RailCom local detector dcc sense pin

---

method **wait_for_flag** *()*

Wait for the new block state available flag.

The new state available flag is an instance of the asyncio.ThreadSafeFlag class
and when set, it indicates that the block detection state state has changed.
This method waits for the flag to be set. When called from another asynchio thread
that thread will wait pending the setting of the flag.
It must be called from a coroutine.

---

method **get_block_state** *()*

Get the current block state

This returns the current block state. The block state is a tuple of the block
status and any RailCom information available. The block status may be:

- *Device.UNKNOWN* the block state is unknown
- *Device.BLK_CH1* RailCom Channel 1 information has changed.

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
Available in both test_dcccmd and test_dccrc1 modules. Press the user button
to run this from the test_dccrc1 module.

---

function **print_dyn_info** *()*

This prints dynamic information received from
decoders (datagram id 7).
Available in test_dcccmd module.

---

## Commissioning PCBs

### Module test_lcl_bd

This is a free standing module for assisting in commissioning the 4 way local detector board.
It's available in the repository test directory.
It is run directly from Thonny and is not installed on the Pico.

It's useage is covered in the commisioning script.

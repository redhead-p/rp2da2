# rp2da2

This project provides Model Railway Distributed Automation for Raspberry Pi RP2040/RP2350 (and other MicropPython Micro Controller Units).

Automation covers:

* DCC generation for mobile vehicle control (e.g. locomotives).  The command station will be a simple RP2040/RP2350 based module (Pico/Pico2 with or without the wireless option).
* Communications with other modules using wireless or wired connections.
* Provision for accessory control.

RailCom is used for:

* block occupancy detection along side conventional current based detection,
* support of Programming on Main (POM),
* collection of additional RailCom information such as actual speed from RailCom decoders.

Currently communications between modules uses [MQTT]([https://mqtt.org|). MQTT follows a publish and subscribe model and requires a broker. The test environment uses the [Mosquitto](https://mosquitto.org) broker running on a Raspberry Pi.

Software is modular. Some software modules will support specific functionality e.g. DCC generation or RailCom response interpretation. Others will be more general and provide a common infrastructure (e.g. MQTT).

For development purposes, testing has been conducted in conjunction with [JMRI](https://www.jmri.org) using its MQTT interface. As result of this, using the software with the standard examples in the repository, will work directly with JMRI. JMRI 'throttles' may be used to control locomotives with mobile decoders. RailCom channel 1 and channel 2 responses are available within JMRI tables.

---

## General Overview

The software is written and developed using [MicroPython](https://micropython.org). Version 1.26 or later Micropython runtime is required. All software dependencies are resolved
using modules within this repository or modules built into the standard MicroPython runtime.

The run-time application is split accross three packages. [Package documentation](docs/SoftwarePackages.md) provides further details. In addition to packaged modules there are example `main.py` modules and test modules.
The packages and other softare need to be installed on the target device. This is covered under [Software Installation](docs/SoftwareInstallation.md).

Setting up local installation details such as network and operational paramaters is described in the [configuration section](docs/Configuration.md).

The hardware environment primarily uses Raspberry Pi Pico or Pico2 processeors.
More detail is provided in the [hardware section](docs/Hardware.md).

High level softare design is covered in the [design document](docs/Design.md).

---

## Repository Structure

Each software package has a directory:

* lib - common software modules
* mqtt - MQTT related software and Wi-Fi modules
* rp2dcc - DCC and RailCom softare modules.

In addition to the package directories, there are three other software directories:

* conf - Example configuration files.
* examples - Example `main.py` modules.
* test - Free standing test and commissioning modules.

The docs directory contains project documentation.

---

## API

### Module dcc_command

## Configuration

---
class **DCCCommand** *(DCC_pn, sleep_pn, gen_sm_num, enable_pn)*

Parameters

* *DCC_pn* Pin number allocated for DCC output.
* *sleep_pn* Pin number allocated to the booster for powering the track
* *gen_sm_num* PIO state machine number to be used for DCC Generation
* *enable_pn* Pin number to enable the DRV8874.

---

method **power** *(p=None)*

DCC Power On/Off

Start and stop command packet transmission scheduling.

Changing the power state will cause the new power state available flag to be set.

Parameters

* *p* 1 for power on, 0 for power off, None for get power status

Returns

* power status as held by the DCC generator.

---

method **read_cv** *(address, cv_num)*

This initiates reading a CV using Programming on Main in conjunction with RailCom.
The command is validated and the read request scheduled for action. The addressed decoder must be
active and the command will be rejected by the command generator class this is not true.

The CV value will be displayed on the OLED.

Parameters

* *address*
* *cv_num* cv number as entered - users count from 1, DCC counts from 0!

---

method **write_cv** *(address, cv_num, new_val)*

This initiates writing a CV using Programming on Main in conjunction with RailCom.

The command is validated and the write request scheduled for action. The addressed
decoder must be active and the command will be rejected by the command generator class
this is not true.

The updated CV value will be displayed on the OLED if the write is successful.

Parameters

* *address*
* *cv_num* cv number as entered - users count from 1, DCC counts from 0!
* *new_val* the new value for the CV

---

method **set_fg1** *(address, f_num, state)*

Set Function Group 1

This sets or clears a function in group 1. The forward light is usually function number 0.

See NMRA S-9.2.1 Section 2.3.4

Parameters

* *address* the address of the decoder - may be short or long
* *f_num* function number to set or clear
* *state* 1 for set, 0 for clear

Returns

* True if validation is passed and the packet is scheduled for transmission. False if validation fails.

---

method **set_speed** *(address, dir, speed)*

Set Speed.

This sets the direction and speed. Direction may be forward or reverse.

The packet generated will be for a 128 step speed setting and decoders must be configured for
28/128 speed steps.

See NMRA S-9.2.1 Section 2.3.2.1

Parameters

* *address* the address of the decoder - may be short or long
* *direction* 1 for forward, -1 for reverse
* *speed* the speed to be set - range 0 to 127

Returns

* True if validation is passed and the packet is scheduled for transmission. False if validation fails.

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

* *blk_name* the name of the block
* *rc_sm_num*  the first state machine number
* *rx_pin* the RailCom local detector rx data pin
* *led* the led number on the led string associated with the block
* *dcc_pin* the RailCom local detector dcc sense pin

---

method **wait_for_flag** *()*

Wait for the new block state available flag.

The new state available flag is an instance of the `asyncio.ThreadSafeFlag` class
and when set, it indicates that the block detection state state has changed.
This method waits for the flag to be set. When called from another asynchio thread
that thread will wait pending the setting of the flag.
It must be called from a coroutine.

---

method **get_block_state** *()*

Get the current block state

This returns the current block state. The block state is a tuple of the block
status and any RailCom information available. The block status may be:

* `Device.UNKNOWN` the block state is unknown
* `Device.BLK_CH1` RailCom Channel 1 information has changed.

RailCom information, if available, is a tuple:

* *address type* 's', 'l' or 'c' for short, long or consist
* *address* as an integer number
* *orientation* 1 or -1

---

method **get_error_counts** *()*

Get Error Counts

Counts of errors are kept. Broadly errors are communication errors or content errors. Content errors
may be caused by faulty decoders, but typically are the result of undetected communicaton errors.

RailCom communication errors are:

* Overrun error (missing stop bit)
* Hamming Weighting high or low (not 4)

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

This is a free standing module for assisting in commissioning the 4 way
local detector board.
It's available in the repository test directory.
It is run directly from Thonny and is not installed on the Pico.

It's useage is covered in the commisioning script.

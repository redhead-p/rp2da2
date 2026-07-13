# API

This section provides API details for key DCC and RailCom modules. Additional detail on
internal interfaces and overall softare design is in the [Full API Documentation](rp2_api/index.html)

## Module dcc_command

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

## Module dcc_rc_ch1

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

Counts of errors are kept. Broadly errors are communication errors or content errors.
Content errors may be caused by faulty decoders, but typically are the result of
undetected communicaton errors.

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

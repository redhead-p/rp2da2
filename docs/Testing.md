# DCC Diagnostics & Testing

## DCC Test Harness

There is a test harness test_dcccmd.py in the test directory.
This may be run using Thonny. Load this into the Thonny editor window and ‘Run current script’
(green play button).
It creates the DCCCommand object (named dcc) and enables RailCom channel 2 global detection.

If OK you will get an invitation to type at the REPL, but the program will still be
running in the background. The OLED display shows a ’splash’.

You can enter DCC API commands at the REPL preceded by
'dcc.'. E.g.:

```py
>>> dcc.power(1)
```

See [API](API.md) for more details.

## RailCom and Detector Test Harnesses

There are test harnesses for these in the test directory.

***test_dccrc1.py*** runs the local RailCom detectors.

***test_quad_blk.py*** runs the current based occupancy Train detectors.

Both may be run using Thonny. Load the program into the Thonny editor window and ‘Run current script’
(green play button).
It creates the channel 1 block detector objects or current based detector for the blocks.

The program will run forever.

Block occupancy details will be displayed on the OLED screen. Press the user button to see RailCom stats.

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

There are two modules in this category. They are available in the repository test directory.
They are run directly from Thonny and is not installed on the Pico.

### Module test_lcl_bd

This is a free standing module for assisting in commissioning the 4 way
local detector board.

### Module test_cs_bd

This is a free standing module for assisting in commissioning the integrated
command station.

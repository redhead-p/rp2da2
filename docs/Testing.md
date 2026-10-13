# Commissioning & Testing

## DCC Test Harness

There is a test harness `test_dcccmd.py` in the test directory. This module
requires the [packages](SoftwarePackages.md) to be installed.

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

There are test harnesses for these in the test directory. These modules
require the [packages](SoftwarePackages.md) to be installed.

`test_dccrc1.py` runs the local RailCom detectors.

`test_quad_blk.py` runs the current based occupancy Train detectors.

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

## Runtime Diagnostics

The lib package diagnostics module includes an event loging feature. When
the main application is run from the REPL rather than as an embedded application
events may be logged using print - defaulting to REPL out.

The logging is controlled using `sys.argv` item 1.

The first item may be set to a character string. Each character in the string enables logging
reports from a specific source as identified in the base Device class.

Characters are:

- w: wifi
- m: MQTT
- l: local RailCom detector
- d: block occupancy detector
- g: global detector

E.g. setting the first argument to 'wm' will log both wifi and mqtt events.
Settings are case sensitive and must be lower case.

To set sys.argv from the REPL prompt, the relevant `main.py` must loaded into the Thonny editor window.
At the REPL prompt enter:

```.py
    __import__('sys').argv.append('wm')
```

This will set the first sys.argv item to `'wm'`.

Then enter:

```.py
        %run -c $EDITOR_CONTENT
```

This will run the current script. Note the lower case 'r'. This omits the soft reset which would
otherwise clear argv!

## Commissioning PCBs

There are two modules in this category. They are available in the repository test directory.
They are run directly from Thonny and are not installed on the Pico. They are self-contained and have no dependencies on external packages.

***test_lcl_bd.py***

This is a free standing module for assisting in commissioning the 4 way
local detector board.

***test_cs_bd.py***

This is a free standing module for assisting in commissioning the integrated
command station.

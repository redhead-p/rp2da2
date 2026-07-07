# Software Installation

## General

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

## Command Station

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

## Block Detector

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

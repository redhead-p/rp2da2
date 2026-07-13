# Software Packages

There are three software packages in this repository. The 'lib' package provides
a common substrate covering:

- a simple user display interface for diagnostic and
    similar features,
- light emitting diodes for status indication, hardware
    configuration and
- base abstractions for hardware device drivers etc.

The 'rp2dcc' package covers DCC and RailCom, providing:

- simple DCC command
station functions,
- RailCom Global/channel 2 response interpretation,
- RailCom Local/channel 1 block detection and
- conventional current based block occupancy detection.

The 'mqtt' package provides remote communications using MQTT and
Wi-Fi.

In addition to the packages there are example main.py and configuration files for the integrated Pico based command station and the quad RailCom local detector.

The following sections provide an overview of the packages. Further details on the
packages and their component modules are provided
in the full [API section](rp2_api/index.html)

---

## lib package - Utility & UI

**device** - This provides the Device class, a base class for hardware device
drivers and similar objects.

**diagnostics** - This provides the singleton HeartBeat class and the logger function.

**hw_conf** - This configures the Pico hardware.

**oled0_91** - Module for 0.91 inch OLED on i2c0

**led_pio** - Module to drive ws2812 LEDs or similar.  A string of up to five LEDs is supported.
The first LED displays the backend communications state. Additional LEDs display the
command station track status or local block status as appropriate.

**screen** - This is the screen application module. It specifies the Screen class.

## mqtt package - communications

**mqtt_client** - This provides a simple MQTT client. Use of MQTT requires an MQTT broker. E.g Mosquitto. There are ports
of this for Windows, MAC/OS, and Linux (e.g. Ubuntu, Raspberry Pi OS).

**mqtt\*** - Other MQTT modules provide interfaces for MQTT devices and agents.
These may be used with JMRI but JMRI MQTT specifications will need to be
changed from the default. Initially we support cabs, power and blocks.
Blocks include occupancy sensor and RailCom reporter.

**wifi** - This acts as wrapper for the standard MicroPython network/Wi-Fi functions.

## rp2dcc package - DCC and Railcom

These modules are dependent on RP2 series processor programable input/output peripherals (PIO)
for DCC command serialisation and RailCom response processing.

### Command Station Modules

**dcc_command** - This module provides high level APIs. It and associated modules contain
the functions and classes for DCC command station.

**dcc_cmd_util** - This module contains classes for DCC command objects.

**dcc_cmd_pio** - This module contains the class and functions for low level
DCC Command Serialisation for use with RailCom detection.

**dcc_rc_ch2** - This module contains the functions and classes for DCC RailCom
command station global detector mobile responses on Channel 2.

**trk_mon** - This module monitors the booster and track status by looking at the DRV8874
sleep, enable, fault and current sense pins.

### Local RailCom Detector Modules

**dcc_rc_ch1** - This module contains the functions and classes for DCC RailCom
block detection on Channel 1.

**blk_mon** - This module contains classes for block occupancy detection based on current
consumption. It works in parallel with the RailCom Channel 1 detector.

### Common Module

**dcc_rc_pio**  - This module contains the functions and classes for low level
RailCom datagram reading. It's applicable for block occupancy detection on
Channel 1 and central dcc command decoder responses on Channel 2.

# Software Installation

## General

The first step in software installation is to obtain a copy of the softare from the [GitHub repository](https://github.com/redhead-p/rp2da2#). You can either clone the repository on your local PC or download a zip file. Either way you should end up with a local copy of the
repository. This includes test and commissioning software, the RP2DA2 'embedded' application, template configuration files and the documentation of which this is a part.

If you have not installed the MicroPython runtime system on the target Pico, this needs to be done now. [Thonny](https://thonny.org) can do this. Select Thonny Settings and then the Configuration tab. This should have an option to install or update MicroPython. You may need to press the Pico's 'bootsel' button before connecting the USB cable to make sure that the Pico is in the correct mode. Complete the details on the 'Install or update MicroPython' screen. The target volume should be preset. The family is 'RP2'. Select the variant that applies to the target Pico and the latest version.

## Configuration Files

Use Thonny to copy repository's conf directory and its contents to the Pico. The target directory is named conf too.  After copying the files should be edited to reflect local requirements. Futher details are in the [Configuration Section](./Configuration.md).

## Install MicroPython Modules

There are three packages to be installed on the target Pico, and also the 'main.py' module. The 'main.py' module is specific to the type of board (e.g. command station or local detector). The [packages](./SoftwarePackages.md) apply to all boards. There is a commissioning module to install the packages and main.py, but manual installation using Thonny is also possible.

### Automated Installation

This is the recommended method for normal installations. It installs direct from GitHub so you will get the latest software. However it will only work on Pico Wireless variants.

It uses [MicroPython Package Management](https://docs.micropython.org/en/latest/reference/packages.html).



### Manual Installation

Copy the python (.py) files from the lib, rp2dcc and mqtt directories to the Pico using Thonny.
Don’t replicate the repository directory structure. Copy the files from the three directories to the
lib directory at the Pico files system top level.
Note that MicroPython will only search the top level directory and the lib directory for
*.py files.
Don’t bother with the \_\_init\_\_.py  files.
These are purely documentary at the moment. Ignore the package.json files.  These define the packages for automated installation.
Also ignore the test directory.


#### Command Station

The main.py in the examples/command directory is a command station version. It provides MQTT connectivity
allowing the command station to be controlled from JMRI or similar.
Copy this main.py from the command directory to the top level directory on the target device.

#### Block Detector

The main.py script in the examples/quad_local_detect directory is the block detector version.

It provides MQTT connectivity
allowing the block detector to report to JMRI or similar.
Copy the main.py from the quad directory to the top level directory on the target device.

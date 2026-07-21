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

Currently communications between modules uses [MQTT]([https://mqtt.org). MQTT follows a publish and subscribe model and requires a broker. The test environment uses the [Mosquitto](https://mosquitto.org) broker running on a Raspberry Pi.

Software is modular. Some software modules will support specific functionality e.g. DCC generation or RailCom response interpretation. Others will be more general and provide a common infrastructure (e.g. MQTT).

For development purposes, testing has been conducted in conjunction with [JMRI](https://www.jmri.org) using its MQTT interface. As result of this, using the software with the standard examples in the repository, will work directly with JMRI. JMRI 'throttles' may be used to control locomotives with mobile decoders. RailCom channel 1 and channel 2 responses are available within JMRI tables.

---

## General Overview

The software is written and developed using [MicroPython](https://micropython.org). Version 1.26 or later Micropython runtime is required. All software dependencies are resolved
using modules within this repository or modules built into the standard MicroPython runtime.

The run-time application is split accross three packages. [Package documentation](docs/SoftwarePackages.md) provides further details. In addition to packaged modules there are example `main.py` modules and test modules.
The packages and other softare need to be installed on the target device. This is covered under [Software Installation](docs/SoftwareInstallation.md).

Setting up local installation details such as network and operational paramaters is described in the [configuration section](docs/Configuration.md).

The hardware environment primarily uses Raspberry Pi Pico or Pico2 processors.
More detail is provided in the [hardware section](docs/Hardware.md).

High level softare design is covered in the [design document](docs/Design.md).

Full API details and additional design information are in the [API section](docs/rp2_api/index.html). This documentation is generated from Python 'docstrings' in the code modules. There are also API details for [key components](docs/API.md).

Details of diagnostics and testing are in the [testing section](docs/Testing.md)

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

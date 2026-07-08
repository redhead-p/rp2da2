# Software Design Overview

This project is a modular firmware framework for distributed model railway automation on
Raspberry Pi RP2040/RP2350 devices running MicroPython. The software is organised
around discrete hardware modules such as an integrated command station and a four channel local RailCom detector. There are target hardware specific modules for the likes of DCC generation track monitoring and a common set of modules for RailCom-based detection, MQTT communication, diagnostics, and local user feedback.

## Design Goals

The software is designed to be:

- Modular, so each subsystem can be developed and tested independently.
- Hardware-oriented, with direct support for RP2 PIO, GPIO, LEDs, OLED displays, and RailCom interfaces.
- Event-driven, using queues and asynchronous tasks rather than a large monolithic loop.
- Suitable for distributed automation, where multiple nodes exchange state over MQTT.

## High-Level Architecture

The firmware is split into three main layers:

1. Hardware and device layer
   - Low-level support for pins, PIO state machines, displays, LEDs, and board-specific configuration.
   - The device abstraction provides a common event model for hardware devices and software agents.

2. Automation and control layer
   - DCC command generation and scheduling.
   - RailCom block detection and occupancy reporting.
   - Track monitors and local command processing.

3. Communications and application layer
   - MQTT client and topic-based agents for remote control and status reporting.
   - Example applications that demonstrate command station behavior and local detection use cases.

## Runtime Model

The firmware is written for the RP2040/RP2350 dual-core architecture:

- Core 0 handles interrupt-driven hardware activity, asynchronous tasks, MQTT processing, and DCC scheduling.
- Core 1 runs the main display and monitoring loop, updating the screen, LED indicators, from event reports.

This split keeps time-critical hardware activity separate from UI and monitoring tasks while still allowing the system to behave as a single application.

## Core Software Components

The key softare components are illustrated in the UML component diagram.

![UML Component Diagram](softwaredesign.svg)

### Device Drivers

The base device layer provides a shared mechanism for registering devices, raising events, and passing those events through a queue. This makes it possible for hardware interrupts and background tasks to report changes without tightly coupling them to the main application loop.

### DCC subsystem

The DCC subsystem is responsible for generating command packets for locomotives and managing power to the track. It uses RP2 PIO hardware for efficient DCC signal serial transmission and supports command scheduling for speed, function, and Programming on Main operations.

### RailCom and Occupancy Detection

RailCom-related classes interpret global and local detector events and track occupancy information. They convert raw detector activity into structured block state reports that can be forwarded to the rest of the system.

### Communications layer

Inititally the communications layer uses MQTT in conjunction with Wi-Fi. The MQTT subsystem provides a small publish/subscribe framework for distributed control. MQTT agents subscribe to specific topics, handle incoming commands, and publish status or event information. This allows the command station to interoperate with tools such as JMRI and other automation nodes without requiring a custom protocol. The agents provide command translation and message routing between the external modules and the local hardware device driver modules.

### Diagnostics and user feedback

The diagnostics module provides heartbeat and event logging, while the display and LED modules present operational state to the user. This makes the firmware easier to debug and gives the operator a simple view of the current state of the system.

## Data Flow

A typical control path looks like this:

1. A hardware event occurs, such as a RailCom response, track change or communications link status change.
2. The event is wrapped as a device report and placed on the shared event queue.
3. The main core 1 application loop or relevant service picks up the event and updates state.
4. If the event is relevant to remote systems, a inter task event is raised so that
the MQTT layer may publish it.

## Extensibility

The codebase is intentionally structured so new features can be added without reworking the whole system:

- New hardware devices can be introduced through the device abstraction.
- New MQTT agents can be added for additional topics and control paths.
- New DCC capabilities can be added in the DCC package.
- New examples can be created independently from the core firmware.

## Summary

The software design favors clarity and modularity over complexity. It treats the command
station and associated detector modules as a distributed embedded system: local hardware
handling is kept close to the device, control logic is separated into focused subsystems,
and networked communication is handled through MQTT.

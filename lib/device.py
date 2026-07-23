"""Device Module
    :author: Paul Redhead


This provides the Device class, a base class for hardware device drivers and
similar objects.


The RP2040 has two cores (0 and 1).  When running MicroPython by default core 0 is used
and core 1 is idle.  The RP2040 port of MicroPython uses the _thread module to run code
in core 1 and enable communications between the cores.


This module provides a queue for passing events and instructions.  Multiple
sources may write to the queue.  There may be only 1 reader.  The reader runs in the main loop.
Sources are typically event driven and use a combination of hardware interrupts and 
timer call-backs.

In the RP2 MicroPython implementaton all interrupts (both hard and soft) are processed in
core 0. Core 1 always runs in non - interrupt context.

If using both cores, the structure of the application has to be designed to accomodate
this.  Device drivers run on core 0. Core 1 runs a main loop which reads the queue and processess entries as they
occur. 

"""
"""       Copyright 2023, 2024, 2025, 2026  Paul Redhead

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

# stardard python imports
from collections import deque
import asyncio

# micropython imports
from machine import Pin
import time, _thread
from micropython import const


MAX_Q_LEN = const(16)
"""The capacity of the event queue."""


class ThreadQError(RuntimeError):
    """Thread Queue Error
    
    Raised to indicate adding to the queue failed due to queue full."""
    pass


class Device():
    """Device Base Class
    
    This class acts as a base for hardware devices and similar. In particular those devices which need to raise 
    events for display on the screen or initiate actions as part of automation.  Events are queued.  Although 
    many devices may raise events there is only one reader.  Typically the device class is a abstract class.  I.e not
    instantiated independently.
    
    Attributes:

        LCL_DEV_TYPE  : Local RailCom Device Type
        GBL_DEV_TYPE  : Global RailCom Device Type
        BD_DEV_TYPE   : Block Detect Device  Type
        BLK_EMPTY: Block unoccupied
        BLK_CH1: Block occupied - RailCom channel 1 info.
        BLK_OCC: Block occupied - Load detected but no info.
        BLK_NPOW: Block not powered.
        POM_CV:  event code for reporting a CV value from read or write.
        POM_TO:  event code for reporting POM access timeout.
        POM_NAK: event code for reporting NAK received.
        MC_DEV_TYPE   :  MQTT Client device type
        MC_CONNECTED : Broker connected
        MC_CLOSED    : Closed
        MC_READY  : Initial subscriptions registered and broker available
        MC_PROT_ERR  : Protocol error - ill formed response etc
        MC_PINGERR   : Ping cannot be sent (wrong state)
        MC_PUB_RX    : Publication received
        MC_READY   : Initial subscriptions registered / no publication in progress
        MC_SEND : Sending (connection request, subscription, or publication)
        WF_DEV_TYPE    : Wi-Fi device type (w)
        WF_DISCON       : Wi-Fi disconnected
        WF_CONNECTING  : Connection in progress
        WF_CONNECTED   : Connected OK
        WF_START       : Wi-Fi starting
        CH2_Q_FULL : Channel 2 report queue full
        MC_U_ID7 : no encoding info for ID7 subindex
        MC_OS_ERR : OS Error on write or read
        TO_DEV_TYPE : Turnout/Point device type
        TO_STATE : Turnout/Point state update

    """
    # class variables

    # device event codes 0 & 1 are allocated for hardware devices with binary states e.g. points & relays etc
    UNSET = const(0)
    """State unset / off / false"""
    SET = const(1)
    """State Set / on / true or action complete if > 2 operables states"""
    UNKNOWN = const(2)
    """State unavalable (e.g start of day"""
    INDETERMINATE = const(3)
    """State indeterminate (e.g. action in progress)"""

    # device specific states

    # RailCom channel 1, local detector & occupancy detector

    LCL_DEV_TYPE    = const('l') # Local RC Dev Type
    BD_DEV_TYPE     = const('d') # Block Detect Dev Type

    BLK_EMPTY = const(20)   # Block unoccupied
    BLK_CH1   = const(21)   # Block occupied - RailCom channel 1 info
    BLK_OCC   = const(22)   # Block occupied - Load detected but no info
    BLK_NPOW  = const(23)   # Block no power

    # RailCom channel 2, global detector

    GBL_DEV_TYPE    = const('g') # Global Device Type

    POM_CV    = const(30)   # CV value from read or write
    POM_TO    = const(31)   # POM access timeout
    POM_NAK   = const(32)   # POM access NAK
    CH2_Q_FULL = const(33)  # Channel 2 report queue full
    
    # MQTT Client

    MC_DEV_TYPE     = const('m')
    MC_CONNECTED    = const(40) # connected
    MC_OS_ERR       = const(41) # OS Error on write or read
    MC_SEND         = const(42) # sending (connection req, sub, or pub)
    MC_READY        = const(43) # initial subscriptions registered / no pubs in progress
    MC_CLOSED       = const(44) # closed
    MC_PINGERR      = const(45) # Ping cannot be sent (wrong state)
    MC_PUB_RX       = const(46) # Publication received
    MC_PROT_ERR     = const(48) # MQTT protocol error 
    MC_U_ID7        = const(49) # no encoding info for ID7 subindex

    # WiFi

    WF_DEV_TYPE    = const('w')
    WF_DISCON      = const(50) # Wi Fi disconnected
    WF_CONNECTING  = const(51) # connection in progress
    WF_CONNECTED   = const(52) # connected OK
    WF_START       = const(53) # wi-fi starting

    # Point 

    TO_DEV_TYPE = const('p')
    TO_STATE  = const(60) # Point state update

    # _fido = WDT()  # enable a watch dog timer just in case

    _queue = deque((), MAX_Q_LEN, 1)

    _q_lock = _thread.allocate_lock()

    ## empty device table
    # will be added to by devices when instantiated.
    _device_table = {}

    @classmethod 
    def by_type_name(cls, type, name):
        """Find a device object by type and name
        
        Args:
            cls:
            type: the type of the device
            name: the name of the device
            
        Returns:
            refererence to the object
            
        Raises:
            IndexError if not found"""
        return cls._device_table[(type, name)]
    
    @classmethod
    def get_items(cls):
        """Get items from the device table.

        The device table holds a list of the device objects keyed by their type and
        name.
        
        returns:
            a list of items - name and device object pairs"""
        return cls._device_table.items()
    
    @classmethod
    def get_keys(cls):
        """Get device names (keys) from the device table.

        The device table holds a list of the device objects keyed by their name.
        
        returns:
            a list of device names"""
        return cls._device_table.keys()
    
    @staticmethod
    def check_core0():
        """Check on core 0
        
        'Soft' ISRs associated with timer events and hw related ISRs now appear to run in core 0.
        This implentation assumes this and the method here allows a 'soft' serivice routine to check
        it's on core 0. The get_ident method return core number + 1!
        
        raises:
            Run time error if not on core 0."""
        if _thread.get_ident() != 1:
            raise RuntimeError( "Wrong core")
    
    @classmethod
    def get_event_report(cls, wait = True):
        """ get the event report at top of queue
        
        This is synchronous if wait true and will wait forever while the queue is empty.
        If wait is false it returns None immediately if the queue is empty.
        
        If the queue is not empty the returned tuple holds:
        
            - source, 'self' from the object reporting the event
            - event, one of ACTION_DONE, ACTION_ERROR, ACTION_INIT or as defined for device
            - data, depends on source object and event

        Args:
            wait:   if True wait for an event report otherwise return immediately

        Returns:
            None or a tuple
        """
        event = None
        while event is None:
            with Device._q_lock:
                try:
                    event = cls._queue.popleft()
                except IndexError:
                    if not wait:
                        time.sleep_ms(0)
                        return None
            time.sleep_ms(1)
        return event
        
    def __init__(self, name, type):
        """Initialise Device

        This initialises the device.  Usally invoked by super().__init__() from the child.

        Save the name (should be unique but not formally tested) & type.  Type is a single character. Could
        used __class__ but that would be more complex.

        Args:
            name: string containing the device name
            type: character specifying the type of device (i.e. class of child)
        """
               
        self._ready_flag = asyncio.ThreadSafeFlag() # used to signal to agent

        self._name = name
        self._type = type
        Device._device_table[(type, name)] = (self)

    @property
    def name(self):
        """Get the device name

        returns:
            the device name as a string
        """
        return self._name
    
    @property
    def type(self):
        """Get the device type

        returns:
            the device type as a single character string
        """
        return self._type

    def report_event(self, event, data):
        """ Add event report to the queue

        The event report is added to the queue.

        :raise ThreadQError:  The queue is full

        args:
            event:  event code - a Device class constant
            data:   event data to qualify code - device dependent  
        """
        with Device._q_lock:
            try:
                Device._queue.append((self, event, data))
                return
            except IndexError:
                pass
        raise ThreadQError('Q full')
    
    async def wait_for_flag(self):
        """ Wait for available event

        This may be called by an agent to wait for the asynchio event to be set
        signifying the device has new information available.
        """
        await self._ready_flag.wait()
        return

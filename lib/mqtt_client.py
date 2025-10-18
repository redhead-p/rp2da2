"""MQTT Client

:author: Paul Redhead

This module contains the MQTT client code. It defines classes for the MQTT Client and messages to be sent
to the MQTT broker.

The MQTT client is a singleton.

MQTT version 3.1.1 as documented https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html
        
QoS2 not supported - only QoS0 or 1

Sessions are clean - i.e. no context saved between sessions. 

Optional client disconnects are not implemented. Unless an error occurs or the broker terminates the 
session the session remains open until power is removed!

The same logic applies to subscriptions - unsubscribe is not implemented.

Authentication is not implemented.

Subscriptions are static.  The subscription list is loaded by the client at instantiation and is
immutable.
"""
"""       Copyright 2023, 2024, 2025  Paul Redhead

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

# python imports
import json, asyncio

# microPython imports
from micropython import const


# lib imports
from device import Device
from led import Led, TriLed
from wifi import WiFi

MQTT_BROKER_PORT = const(1883)
""" Default MQTT broker port number
This is the default port number for the MQTT broker. It can be overridden in the configuration file.
"""

_CONNECT     = const(1) # Client to Server - Connection request
_CONNACK     = const(2)  # Server to Client - Connect acknowledgment
_PUBLISH     = const(3)  # Client to Server or Server to Client - Publish message
_PUBACK      = const(4)  # Client to Server or Server to Client - Publish acknowledgment (QoS 1)
_PUBREC      = const(5)  # Client to Server or Server to Client - Publish received (QoS 2 del. pt. 1)
_PUBREL      = const(6)  # Client to Server or Server to Client - Publish release (QoS 2 del. pt. 2)
_PUBCOMP     = const(7)  # Client to Server or Server to Client - Publish complete (QoS 2 del. pt. 3)
_SUBSCRIBE   = const(8)  # Client to Server - Subscribe request
_SUBACK      = const(9)  # Server to Client - Subscribe acknowledgment
_UNSUBSCRIBE = const(10) # Client to Server - Unsubscribe request
_UNSUBACK    = const(11) # Server to Client - Unsubscribe acknowledgment
_PINGREQ     = const(12) # Client to Server - PING request
_PINGRESP    = const(13) # Server to Client - PING response
_DISCONNECT  = const(14) # Client to Server or Server to Client - Disconnect notification
_AUTH        = const(15) # Client to Server or Server to Client - Authentication exchange

_REOPEN_TIME = const(5000)    # wait 5 seconds 
_KEEP_ALIVE  = const(60)   # 60 seconds as far as broker is concerned but
_PING_TIME   = const(50000)  # we will send ping after 50 secs of inactivity
_ACK_TIME    = const(10000) # the broker should respond within a 'reasonable' time

_MAX_MUX = const(128 * 128 * 128)


class MQTTPacketOut():
    """MQTT Control Packet Out

    This class is used to construct MQTT control packets to be sent to the
    broker.
    It provides methods to add bytes, strings and payloads to the packet.
    The packet is constructed as a bytearray and the write method sends the
    complete packet.
    The first byte is the control packet type and flags, the second byte
    is the length of the packet.
    The length is calculated as the number of bytes in the packet minus 2
    (the first two bytes).
    The packet is constructed in the order of the MQTT protocol specification.
    """

    def __init__(self, pkt_type, flags = 0):
        """Construct MQTT Control Packet out

        Set  up first byte as control packet type and flags.
        Initialise second byte (length) to 0

        Args:
            self:
            pkt_type:   MQTT Control Packet type
            flags:      
        """
        self._buffer = bytearray(((pkt_type << 4 | flags & 0xf),0))

    def add_byte(self, b):
        """Add a byte to the packet

        Args:
            b: the byte to add to the packet
        """
        self._buffer.append(b)

    def add_uint16(self, i):
        """Add a 16 bit unsigned integer to the packet

        Args:
            i: the integer to add to the packet
        """
        self._buffer.append(i >> 8)
        self._buffer.append(i & 0xff)

    def add_str(self, s):
        """Add a string to the packet

        The string is added as a UTF-8 encoded byte string.
        The length of the string is added as a 16 bit unsigned integer.
        Args:
            s: the string to add to the packet
        """
        l = len(s)
        self._buffer.append(l >> 8)
        self._buffer.append(l & 0xff)
        self._buffer.extend(bytes(s, 'utf-8'))

    def add_payload(self, s):
        """Add a payload to the packet

        The payload is added as a UTF-8 encoded byte string.
        Args:
            s: the payload to add to the packet
        """
        self._buffer.extend(bytes(s, 'utf-8'))

    async def write_buff(self, writer):
        """Write the complete packet

        The first byte is the control packet type and flags, the second byte is the length of the packet.
        The length is calculated as the number of bytes in the packet minus 2 (the first two bytes).
        
        args:
            writer: the write stream
        
        Returns:
            True if write successful else False
        """
        self._buffer[1] = len(self._buffer) - 2
        try:
            writer.write(self._buffer)
            await writer.drain()
        except OSError:
            return False
        return True


class MQTTClient(Device):
    """ MQTT Client
    
    This is a simplified version of an MQTT Client. Quality of Service 2 is not supported.
    
    Subscriptions are pre-defined and set up on connection.  Dynamic modifications to subscriptions
    not supported.
    
    It is a singleton.

    The client is started by calling the start method with a list of MQTTSubscription objects.
    The client will connect to the MQTT broker and subscribe to the topics defined in the subscription list.
    The client will then listen for incoming messages and handle them according to the subscription list.

    asyncio.Streams are used for reading and writing.

    Attributes:
        QoS_MASK:  mask for QoS bits
        RETAIN: MQTT retain flag     
        DUP: MQTT duplicate flag   
        PROTOCOL_LVL: MQTT Protocol Level 4 (MQTT version 3.1.1)
        M_CLOSED: no connection
        M_CONNECTING: new connection - waiting for CONNACK
        M_SUBSCRIBING: new connection - waiting for SUBACK
        M_CONNECTED: status connected (and subscribed)
        M_PING_SENT: connected - waiting for PINGRESP
        M_REJECTED:  connection rejected by broker (it will terminate it!)
        ERR_LEN: ill formed length field
        ERR_P_TYPE: unrecognised packet type
        ERR_CONACK: invalid connection acknowledgement
        ERR_PINGRESP: invalid ping response
        ERR_PUBACK : invalid publish acknowledgement
        ERR_SUBACK: invalid subscription acknowledgement
        ERR_UTF8: invalid UTF8 character
        DEVICE_TYPE: MQTT client device type
        QoS0: Quality of service 0
        QoS1: Quality of service 1
        errors: counts of errors by type
    """

    QoS_MASK    = const(0x06) # mask for QoS bits
    RETAIN      = const(1)
    DUP         = const(8)

    PROTOCOL_LVL  = const(0x04)  # Protocol Level 4 (MQTT version 3.1.1)

    M_CLOSED     =  const(0)       # no connection
    M_CONNECTING =  const(1)       # new connection - waiting for CONNACK
    M_SUBSCRIBING = const(2)       # new connection - waiting for SUBACK
    M_CONNECTED  =  const(3)       # status connected (and subscribed)
    M_PING_SENT  =  const(4)       # connected - waiting for PINGRESP
    M_REJECTED   =  const(5)       # connection rejected by broker (it will terminate it!)

    ERR_LEN = const(1)          # ill formed length field
    ERR_P_TYPE = const(2)       # unrecog packet type
    ERR_CONACK = const(3)
    ERR_PINGRESP = const(4)
    ERR_PUBACK = const(5)
    ERR_SUBACK = const(6)
    ERR_UTF8   = const(7)

    QoS0        = const(0)      # Quality of service 0

    QoS1        = const(1)      # Quality of service 1

    DEVICE_TYPE = const('m')

    _mqtt_client = None  # the singleton instance

    @classmethod
    def get_instance(cls):
        """Return the singleton instance

        The singleton is created on the first call.
        """
        if cls._mqtt_client is None:
            cls._mqtt_client = MQTTClient()
        return cls._mqtt_client

    def __init__(self):
        """Construct the MQTT Client
        
        Getting a reference to the Wi-Fi singleton will instantiate it if not already done.
        """
        if (MQTTClient._mqtt_client) != None and (MQTTClient._mqtt_client is not self):
            raise RuntimeError('only one instance allowed')

        with open('/conf/mqtt.json', 'r') as fd:
            conf = json.load(fd)
        try:
            port = conf['port']
        except KeyError:
            port = MQTT_BROKER_PORT

        self._con_params = conf['broker'], port
        self._client_id = conf['clientId']
        
        self._tri_led = TriLed.get_instance() # this will be None on a Pico

        self._wifi = WiFi.get_instance()

        self._state = MQTTClient.M_CLOSED # don't bother to log the initial state
        self.errors = {}
        self._ping_deferred = asyncio.Event() # normal traffic defers pings

        super().__init__(self._client_id, MQTTClient.DEVICE_TYPE)

    def report_event(self, event, data):
        """Report an event

        This overrides the version in the base class.

        This reports an event. WiFi LED events are shown on the communications LED if available.
        Other events are reported via the device.
        """
        if self._tri_led is None or event != Device.MC_SET_LED:
            super().report_event(event, data)
        else:
            # set the led here.
            self._tri_led.set(data[0], data[1])

    def get_broker(self):
        """ Get the MQTT Broker ID
        
        This returns the MQTT Broker ID as a string.
        """
        return self._con_params[0]
    
    async def run(self, subscription_list):
        """ MQTT Client Run
        
        This coroutine runs the MQTT client. It does not return.

        Args:
            subscription_list: a list of MQTTSubscripion objects to subscribe to
        """
        self._subscription_list  = subscription_list
        while True:
            if self._state == MQTTClient.M_CLOSED:
                await asyncio.sleep_ms(_REOPEN_TIME)
            # attempt to (re)open connection
                await self._re_open()
            while self._state != MQTTClient.M_CLOSED:
                try:
                    hdr = await self._reader.read(2)
                except OSError:
                    await self._close()
                    continue
                if len(hdr) == 2:
                    packet_type = hdr[0] >> 4
                    # packet flags are DUP, QoS, RETAIN 
                    packet_flags = hdr[0] & 0x0f
                    mux = 1 # multiply factor for length
                    nv = hdr[1]
                    # extract the length - this uses continuation bytes if necessary
                    # continuation bytes are read 1 at a time from the stream
                    l = nv & 0x7f
                    while nv > 127 and mux < _MAX_MUX:
                        nv = await self._reader.read(1)[0]
                        mux *= 128
                        l += mux * (nv & 0x7f)
                    if nv > 127:
                        self._log_error((MQTTClient.ERR_LEN, packet_type))
                    if l == 0:
                        packet = bytes(0)
                    else:
                        # read the remainder in one go
                        packet = await self._reader.read(l)

                    try:
                        await MQTTClient._RESP_HANDLER[packet_type](self, packet_flags, packet)
                    except KeyError:
                        self._log_error((MQTTClient.ERR_P_TYPE, packet_type))
                else:
                    # remote close seems to trigger 0 len message
                    # and 1 is too short
                    await self._close()

    async def publish(self, topic, payload,  retain = True, QoS = QoS1):
        """ MQTT Publish

        At the moment we will assume no duplicates will be sent
        it only makes sense to send duplicates if clean session not used.
        I.e. sessions may span connections  - therefore despite use of QoS one  there's
        no need to save the message.

        **TODO** Trap 'no free pid error'

        args:
            topic: MQTT topic
            payload: the payload message to be sent
            retain: boolean
            QoS: Quality of Service
        """
        
        if ((self._state != MQTTClient.M_CONNECTED)
                and (self._state != MQTTClient.M_PING_SENT)):
            return False;      # unlike subscriptions we don't hold publications pending connection
    
        self.report_event(Device.MC_SET_LED, (Led.LED_B, 1))
        flags = (QoS << 1) | (MQTTClient.RETAIN if retain else 0)
    
        packet = MQTTPacketOut(_PUBLISH, flags)
        packet.add_str(topic)

        if QoS > 0:
            # add a currently unused pid
            packet.add_uint16(self._clientPidTx.pop())

        packet.add_payload(payload)
        if await packet.write_buff(self._writer):
            self._ping_deferred.set()
            if QoS == 0:
                # we won't get an acknowledgement so return to idle immediately
                self.report_event(Device.MC_SET_LED, (Led.LED_B, 0), _PUBLISH)
            return True
        await self._close()
        return False
    
    async def _subscribe(self):
        self.report_event(Device.MC_SET_LED, (Led.LED_B, 1))
        packet = MQTTPacketOut(_SUBSCRIBE, MQTTClient.QoS1 << 1)

        # add a currently unused pid
        packet.add_uint16(self._clientPidTx.pop())
        for sub_topic in self._subscription_list:

        # next is the subscribe payload 
            packet.add_uint16(len(sub_topic._topic_filter))
            packet.add_payload(sub_topic._topic_filter)
            packet.add_byte(sub_topic._QoS)
        if await packet.write_buff(self._writer):
            self._ping_deferred.set()
            return True
        await self._close()        
        return False    

    async def _puback(self, pid):
        """ Return PUBACK after receiving PUBLISH"""
        packet = MQTTPacketOut(_PUBACK, 0)
        packet.add_byte(2)
        packet.add_uint16(pid)
        if await packet.write_buff(self._writer):
            self._ping_deferred.set()
            self.report_event(Device.MC_SET_LED, (Led.LED_G, 0))
            return True
        await self._close()        
        return False

    async def _handle_connack(self, pf, packet):
        # flags must be 0
        # conack flags must be 0 for clean session
        # conack result must be 0
        if packet != b'\x00\x00' or pf != 0:
            self._log_error(MQTTClient.ERR_CONACK)
            await self._close()
            return
        self.report_event(Device.MC_SET_LED, (Led.LED_B, 0))
        # allocate 10 pid values for tx usage
        self._clientPidTx = set(range(1, 11))
        self._set_state(MQTTClient.M_SUBSCRIBING)
        await self._subscribe()

    async def _handle_suback(self, pf, packet):
        # flags must be 0
        # conack flags must be 0 for clean session
        # conack result must be 0
        if pf != 0:
            self._log_error(MQTTClient.ERR_SUBACK)
            await self._close()
            return
        self.report_event(Device.MC_SET_LED, (Led.LED_B, 0))
        pid = packet[0] * 256 + packet[1]
        if pid in self._clientPidTx:
            # shouldn't be there if in use!
            self._log_error(MQTTClient.ERR_SUBACK)
            await self._close()
            return
        self._clientPidTx.add(pid) # put back in list as being available.

        self._set_state(MQTTClient.M_CONNECTED)
        self.report_event(Device.MC_READY, None)

    async def _handle_publish(self, pf, packet):
        """PUBLISH received"""
        self.report_event(Device.MC_SET_LED, (Led.LED_G, 1))
        dup_flag = pf & MQTTClient.DUP
        QoS = (pf & MQTTClient.QoS_MASK) >> 1
        ret_flag = pf & MQTTClient.RETAIN
        topic_len = packet[0] * 256 + packet[1]
        # acknowledge publication - with pid extracted from packet
        if QoS != MQTTClient.QoS0:
            await self._puback(packet[topic_len + 2] * 256 + packet[topic_len + 3])
        else:
            # clear led here
            self.report_event(Device.MC_SET_LED, (Led.LED_G, 0))
        try:
            topic = packet[2:2 + topic_len].decode("utf8")
            payload = packet[topic_len+4:].decode("utf8")
        except UnicodeError:
            self._log_error(MQTTClient.ERR_UTF8)
            return # ignore ill formed strings

        for subscription in self._subscription_list:
            if subscription.matches(topic):
                subscription.handle_publication(topic, dup_flag, ret_flag, payload)

    async def _handle_puback(self, pf, packet):
        """PUBACK received
        
        Acknowledgement of PUBLISH QoS1
        """
        if len(packet) != 2 or pf != 0:
            # 2 byte PId but no flags allowed
            self._log_error(MQTTClient.ERR_PUBACK)
            await self._close()
            return
        pid = packet[0] * 256 + packet[1]
        if pid in self._clientPidTx:
            # shouldn't be there if in use!
            self._log_error(MQTTClient.ERR_PUBACK)
            await self._close()
            return
        self._clientPidTx.add(pid) # put back in list as being available.
        self.report_event(Device.MC_SET_LED, (Led.LED_B, 0))

    async def _handle_pingresp(self, pf, packet):
        if packet != b'' or pf != 0:
            # no message or flags allowed
            self._log_error(MQTTClient.ERR_PINGRESP)
            await self._close()
            return
        self.report_event(Device.MC_SET_LED, (Led.LED_B, 0))
        self._set_state(MQTTClient.M_CONNECTED)

    def _log_error(self, error):
        """Log error
        
        Increment a count by error type.
        """
        try:
            self.errors[(error)] +=1
        except KeyError:
            self.errors[(error)] = 1

    async def _close(self):
        """ We only close the stream as part of error recovery"""
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except AttributeError:
            # occurs if writer not created
            pass
        self._set_state(MQTTClient.M_CLOSED)
        self.report_event(MQTTClient.MC_SET_LED, (Led.LED_B, 1))

    async def _re_open(self):
        """Open or Re-open the MQTT connection"""
        if self._wifi.isconnected():
            self.report_event(MQTTClient.MC_SET_LED, (Led.LED_B, 1))
            try:
                self._reader, self._writer = await asyncio.open_connection(*self._con_params)
            except OSError:
                # nothing to close - not opened!
                return
            packet = MQTTPacketOut(_CONNECT)
            packet.add_str('MQTT')
            packet.add_byte(MQTTClient.PROTOCOL_LVL)
            packet.add_byte(0x02)  # clean session
            packet.add_uint16(_KEEP_ALIVE) # keep alive timer
            packet.add_str(self._client_id)
            self._set_state(MQTTClient.M_CONNECTING)
            if await packet.write_buff(self._writer):
                self._ping_task = asyncio.create_task(self._pinger())
                return
            await self._close()
    
    async def _pinger(self):
        """ Coroutine to send a ping
        
        The ping will be sent when the ping timer expires.
        The coroutine will close the connection and terminate if
        the previous ping has not been acknowledged.
        The coroutine will exit if no longer connected. 
        """
        while self._state != MQTTClient.M_CLOSED:
            try:
                await asyncio.wait_for_ms(self._ping_deferred.wait(), _PING_TIME)
            except asyncio.TimeoutError:
                # no activity - send ping
                if self._state != MQTTClient.M_CONNECTED:
                    # somethings gone wrong if initial handshakes / last ping
                    # still in progress
                    await self._close()
                    break

                if await MQTTPacketOut(_PINGREQ).write_buff(self._writer):
                    self._set_state(MQTTClient.M_PING_SENT)
                    self.report_event(MQTTClient.MC_SET_LED, (Led.LED_B, 1))      # Ping response pending
                    continue
                await self._close()
                break # terminate task
            self._ping_deferred.clear()

    def _set_state(self, state):
        self._state = state

    _RESP_HANDLER = {_CONNACK:_handle_connack,
                    _PINGRESP:_handle_pingresp,
                    _PUBACK:_handle_puback,
                    _SUBACK:_handle_suback,
                    _PUBLISH:_handle_publish}

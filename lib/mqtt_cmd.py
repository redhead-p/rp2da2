"""MQTT Control and Utilities

:author: Paul Redhead

This module provides access to the MQTT interface via MQTT agents which manage subscriptions and
publications on behalf of relevant hardware and applications software.

This module provides functions for the command station.  E.g. MQTT Agents for DCC and RailCom Channel 2.

MQTT version 3.1.1 as documented https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html
        
QoS2 not supported - only QoS0 or 1

Sessions are clean - i.e. no context saved between sessions. 

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


from micropython import const

from mqtt import MQTTAgent

from mqtt_client import MQTTClient

from dcc_command import DCCCommand




class Power(MQTTAgent):
    """Manage Power Subscription and publication
    
    There is only one of these, but singularity is not enforced."""

    ON_OFF = {'ON':DCCCommand.ON , 'OFF': DCCCommand.OFF}
    """On Off decode for power and decoder function commands"""

    def __init__(self, topic_filter, QoS, pub_topic):
        """Initialise the power manager

        This initialises the power manager with the topic filter and QoS for the subscription
        and the topic for publishing the power state.

        This will publish the power state when the power state changes or on the first call to check_power.
        It will also publish the power state if a retained message is received.

        Args:
            topic_filter: the topic filter to match against received topics
            QoS: the Quality of Service for the subscription.  Must be either MQTTClient.QoS0 or MQTTClient.QoS1
            pub_topic: the topic used for publishing the power state
        """
        if QoS not in (MQTTClient.QoS0, MQTTClient.QoS1):
            raise ValueError("QoS must be either MQTTClient.QoS0 or MQTTClient.QoS1")
        super().__init__(topic_filter, QoS)
        self._publish_topic = pub_topic
        self._power_state = None    # to indicate first time
        self._dcc = DCCCommand.get_instance()
        


    def handle_publication(self, topic, dup_flag, ret_flag, payload):
        """Handle a publication

        This method is called by the MQTT client when a publication is received. 
        It will turn the DCC power on or off according to the payload.

        Args:
            topic: the topic of the publication
            dup_flag: True if this is a duplicate publication
            ret_flag: True if this is a retained publication
            payload: the payload of the publication as a string
        """

        if ret_flag == MQTTClient.RETAIN:
            # this is a message retained by the broker
            # we won't act on it
            # but send actual state instead
            self._power_state = None # to force power state send on next check
            return
        try:        
            self._dcc.power(Power.ON_OFF[payload])
        except KeyError:
            # invalid payload
            return

    def pub_check(self):
        """ Check for publication.
        
        Publish the power state if first call or changed since last check.

        returns:
            True if the agent has published else False
        
        """
        power = self._dcc.power() # get current power
        tx_payload = "ON" if power == DCCCommand.ON else "OFF"
        if self._power_state is None:
            self._client.publish(self._publish_topic, tx_payload, True, MQTTClient.QoS1)
            self._power_state = power   # save power state for next call
            return
        if power == self._power_state:
            # unchanged
            return False
        self._client.publish(self._publish_topic, tx_payload, True, MQTTClient.QoS1)
        self._power_state = power   # save power state for next call
        return True
        

class Cab(MQTTAgent):
    """Cab Subscription

    This subscription is used to handle publications to the cab topic.
    It is not used to publish a cab message, but to handle the cab message
    when it is received from the broker.

    Cab commands are passed to the DCC system for encodeing and transmission.

    This is a singleton and receives all cab messages. Singularity is not enforced.

    A valid DCC speed command requires both direction and speed, but these are in 
    separate MQTT publications. DCC speed commands are not issued until valid MQTT
    publicatons have been received for both speed and direction.
    """

    DIR_DECODE = {'FORWARD':DCCCommand.FWD, 'STOP':DCCCommand.STOP, 'REVERSE':DCCCommand.REV}
    """Direction decode for decoder direction commands"""

    _cab = {} #dictionary containing speed and direction for known cabs by address.

    def __init__(self, topic_filter, QoS):
        """Initialise the cab subscription
        Args:
            topic_filter: the topic filter to match against received topics
            QoS: the Quality of Service for this subscription.  Must be either MQTTClient.QoS0 or MQTTClient.QoS1
        """
        super().__init__(topic_filter, QoS)
        self._dcc = DCCCommand.get_instance()

    def handle_publication(self, topic, dup_flag, ret_flag, payload):
        """Handle a publication
        This method is called by the MQTT client when a publication is received.
        Args:
            topic: the topic of the publication
            dup_flag: True if this is a duplicate publication
            ret_flag: True if this is a retained publication
            payload: the payload of the publication as a string
        """
        topic_up = topic.split('/') # unpack topic into separate strings
        try:
            address = int(topic_up[1])
        except ValueError:
            # not a number
            return
        cmd = topic_up[2]
        # only function commands have the 4th topic - function number
        try:
            topic3 = topic_up[3]
        except IndexError:
            topic3 = None

        try:
            Cab._CAB_CMD[cmd](self, address, topic3, payload) # self has to be explicitly passed
        except KeyError:
            # ignore unrecognised command topic
            pass

            
    def _handle_fn_pub(self, address, topic3, payload):
        try:
            fn_no = int(topic3)
        except ValueError:
            # not a number
            return
        except IndexError:
            # or number missing
            return
        try:
            state = Power.ON_OFF[payload]
        except KeyError:
            # invalid payload
            return
        # at the moment everything goes to function group 1 so functions higher than 4 are ignored!
        self._dcc.set_fg1(address, fn_no, state)

    def _handle_dir_pub(self, address, topic3, payload):
        try:
            dir = Cab.DIR_DECODE[payload]
        except KeyError:
            # invalid payload
            return
        try:
            # do we have as cab record for this address
            old_dir, dcc_speed = self._cab[address]
        except KeyError:
            #no - it will be created later
            dcc_speed = None
            #self._cab[address] = (dir, dcc_speed)
        if dcc_speed is None:
            # we don't know the speed so command cannot be issued
            if dir !=  DCCCommand.STOP:
                # save the new direction as long as it's not stop
                self._cab[address] = (dir, dcc_speed)
            return
        if dir == DCCCommand.STOP:
            # emergency stop - dcc speed is 1
            self._dcc.set_speed(address, old_dir, 1)
            self._cab[address] = (old_dir, 0)
            return
        # normal command
        self._dcc.set_speed(address, dir, dcc_speed)
        self._cab[address] = (dir, dcc_speed)


        
    def _handle_spd_pub(self, address, topic3, payload):
        try:
             # convert JMRI speed 0 - 100 to DCC speed (1 to 127)
            dcc_speed = (((int(payload) * 126) + 63) // 101) + 1
        except ValueError:
            # not a number
            return

        # but we don't use 1 so set it to 0
        if dcc_speed == 1:
            dcc_speed = 0
        
        try:
            # do we have as cab record for this address
            dir, _ = self._cab[address]
        except KeyError:
            #no create it
            dir = None
            self._cab[address] = (dir, dcc_speed)
        if dir is None:
            # we don't know the direction so command cannot be issued
            # a subsequent command should set it
            return
        # command can be issued
        self._dcc.set_speed(address, dir, dcc_speed)
        self._cab[address] = (dir, dcc_speed)

    def _handle_ns_pub(self, address, topic3, payload):
        pass


    _CAB_CMD = {'throttle':_handle_spd_pub,
                'direction':_handle_dir_pub,
                'function':_handle_fn_pub,
                'consist':_handle_ns_pub}

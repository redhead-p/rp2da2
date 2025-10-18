"""MQTT Control and Utilities

:author: Paul Redhead

This module provides access to the MQTT interface via MQTT agents which manage subscriptions and
publications on behalf of relevant hardware and applications software.

This module provides common functions. e.g. the abstract base class for MQTT agents. 

MQTT version 3.1.1 as documented https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html
        
QoS2 not supported - only QoS0 or 1

Sessions are clean - i.e. no context saved between sessions. 

Subscriptions are static.  The subscription list is passed to the client at instantiation and is
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

import asyncio

from mqtt_client import MQTTClient


from dcc_rc_ch1 import RComBlkDet


class MQTTAgent():
    """ MQTT Agent

    This is a virtual class acting as the base for MQTT agents that set up subscriptions,
    process received publications and publish.
    """


    # too early to call get_instance 
    _dcc = None
    # but OK here because get_instance will instantiate the client
    _client = MQTTClient.get_instance()
    
    def __init__(self, topic_filter, QoS):
        """Initialise the subscription

        Args:
            topic_filter: the topic filter to match against received topics
            QoS: the Quality of Service for this subscription.  Must be either MQTTClient.QoS0 or MQTTClient.QoS1

        """
        self._topic_filter = topic_filter
        self._QoS = QoS
        self._create_pub_check() # create the publication check task

    def matches(self, topic):
        """check if topic matches filter

        Parse the received topic against the topic filter to see if it
        matches.

        '+' matches a single item in the topic name.
        '#' matches any remaining topic name including none

        Args:
            self:
            topic: the received topic as a string

        Returns:
            True if matches else false
        """
        topic_iter = iter(topic.split('/'))
        for filter_item in self._topic_filter.split('/'):
            try:
                topic_item = next(topic_iter)
            except StopIteration:
                 # '#' matches null string but otherwise topic list is too short
                return(filter_item == '#')
                   
            # '#' wild card - must be last and matches rest of topic
            if filter_item == '#':
                return True
            # '+' wild card - matches this item only
            if filter_item != '+' and filter_item != topic_item:
                # neither wild card topic nor match
                return False
        return True
    
    def get_filter(self):
        """Get the topic filter for this subscription
        
        Returns:
            The topic filter as a string
        """
        return (self._topic_filter)
    
    def handle_publication(self, topic, dup_flag, ret_flag, payload):
        """ Handle a publication

        This method is called by the MQTT client when a publication is received.
        It must be implemented by the derived class. 

        Args:
            topic: the topic of the publication
            dup_flag: True if this is a duplicate publication
            ret_flag: True if this is a retained publication
            payload: the payload of the publication as a string
        """
        raise NotImplementedError
    
    def _create_pub_check(self):
        """ Create Publication check task
        
        Creates a task to periodically  check to see if agent has anything to publish and publish it.
        
        This is the default version for those agents that do not publish.
        It should be overridden in the derived class for any agent that publishes.
        """
        return


class Will(MQTTAgent):
    """Will Agent

    The subscription is used to handle the MQTT will message when published by the broker on behalf
    of another client that has gone off line (e.g. jmri). The subscription is remote client specific
    and an instance is required for each remote client to be monitored.
    
    This agent does not publish. 
    """

    def __init__(self, topic_filter, QoS):
        """Initialise the will subscription

        Args:
            topic_filter: the topic filter to match against received topics
            QoS: the Quality of Service for this subscription.  Must be either MQTTClient.QoS0 or MQTTClient.QoS1
        """
        super().__init__(topic_filter, QoS)

    def handle_publication(self, topic, dup_flag, ret_flag, payload):
        """Handle will publication
        
        This method is called by the MQTT client when a will publication is received.

        **TODO** What to do with this?

        retained 1 payload 'OFFLINE' on initial connection indicates JMRI not available
        retained 0 payload 'OFFLINE' during connection indicates JMRI connection now closed
        retained 0 payload '' during connection indicates JMRI now available.

        Args:
            topic: the topic of the publication
            dup_flag: True if this is a duplicate publication
            ret_flag: True if this is a retained publication
            payload: the payload of the publication as a string
        """
        print('will', ret_flag, payload)

class Block(MQTTAgent):
    """Block Agent

    This agent is used to handle publications to the block topic and
    any publications it makes.
    """
    SENSOR_TOPIC_PREFIX = "track/sensor"
    REPORTER_TOPIC_PREFIX = "track/reporter"

    SENSOR_PAYLOAD = {RComBlkDet.BLK_EMPTY:"INACTIVE",
                       RComBlkDet.BLK_OCC:"ACTIVE",
                       RComBlkDet.BLK_CH1:"ACTIVE"}
    
    _ACTIVE_STATE = (RComBlkDet.BLK_OCC, RComBlkDet.BLK_OCC)

    def __init__(self, rc_block):
        self._rc_block = rc_block # RailCom block
        self._name = rc_block.get_name()
        self._last_blk_state = RComBlkDet.UNKNOWN
        super().__init__(f'{Block.SENSOR_TOPIC_PREFIX}/{self._name}/set', MQTTClient.QoS1)

    def _create_pub_check(self):
        """Overrides version in base class"""
        asyncio.create_task(self._pub_check())
        return

    def handle_publication(self, topic, dup_flag, ret_flag, payload):
        """Handle a publication
        This method is called by the MQTT client when a publication is received.
        Args:
            topic: the topic of the publication
            dup_flag: True if this is a duplicate publication
            ret_flag: True if this is a retained publication
            payload: the payload of the publication as a string
        """
        print("Sensor", topic, payload)

    async def _pub_check(self):
        """ Publication check
        
            Check to see if block state has changed and publish it.
        
            This coroutine runs forever.
        """
        while True:
            await self._rc_block.wait_for_flag()

            # Get the new block state from the channel 1 detector
            state, data = self._rc_block.get_block_state()
            # the detector treats OCCUPIED to CH1 data available
            # or vice versa as a state change - but they are both reported as
            # ACTIVE so are ignored here

            if not((state in Block._ACTIVE_STATE)
                    and (self._last_blk_state in Block._ACTIVE_STATE)):
                # Publish the new block state
                try:
                    tx_payload = Block.SENSOR_PAYLOAD[state]
                except KeyError:
                    # not valid status (yet)
                    continue
                if not await self._client.publish(
                        f'{Block.SENSOR_TOPIC_PREFIX}/{self._name}/event',
                        tx_payload,
                        False,
                        MQTTClient.QoS1):
                    continue # publish failed - retry later
            if state == RComBlkDet.BLK_CH1:
                # channel 1 info available - always published 
                # likelyhood of a change without intervening INACTIVE low
                _, address, orientation = data
                await self._client.publish(
                        f'{Block.REPORTER_TOPIC_PREFIX}/{self._name}',
                        f'{address} {orientation}',
                        False, MQTTClient.QoS1)
            elif self._last_blk_state == RComBlkDet.BLK_CH1:
                # clear reporter info
                await self._client.publish(
                        f'{Block.REPORTER_TOPIC_PREFIX}/{self._name}',
                        '',
                        False,
                        MQTTClient.QoS1)
            self._last_blk_state = state

"""MQTT Control and Utilities

:author: Paul Redhead

This module provides access to the MQTT interface via MQTT agents which manage subscriptions and
publications on behalf of relevant hardware and applications software.

This module provides functions specific to the local RailCom detector.

MQTT version 3.1.1 as documented https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html
        
QoS2 not supported - only QoS0 or 1

Sessions are clean - i.e. no context saved between sessions. 

Subscriptions are static.  The subscription list is passed to the client at instantiation and is
immutable.
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

import asyncio

from mqtt_client import MQTTClient
from mqtt import MQTTAgent


from dcc_rc_ch1 import RComBlkDet
from blk_mon import DCCBlkDet


class Block(MQTTAgent):
    """Block Agent

    This agent is used to handle publications to the RailCom topic and
    any publications it makes.
    """
    REPORTER_TOPIC_PREFIX = "rcom/lcl"

    def __init__(self, rc_block):
        """Construct the Block agent
        
        Create object variables and initialise the base Agent class topic and QoS"""
        self._rc_block = rc_block # RailCom block
        self._name = rc_block.name
        self._last_blk_state = RComBlkDet.UNKNOWN
        super().__init__(f'{Block.REPORTER_TOPIC_PREFIX}/{self._name}/set', MQTTClient.QOS1)

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
        pass

    async def _pub_check(self):
        """ Publication check
        
            Check to see if block state has changed and publish it.
        
            This coroutine runs forever.
        """
        while True:
            await self._rc_block.wait_for_flag()

            # Get the new block state from the channel 1 detector
            try:
                _, address, orientation = self._rc_block.block_state
            except TypeError:
                # block state None or otherwise invalid!
                await self._client.publish(
                    f'{Block.REPORTER_TOPIC_PREFIX}/{self._name}',
                    '',
                    False,
                    MQTTClient.QOS1)
            else:
                # channel 1 info available - always published 
                # likelyhood of a change without intervening INACTIVE low
                await self._client.publish(
                    f'{Block.REPORTER_TOPIC_PREFIX}/{self._name}',
                    f'{address} {orientation}',
                    False,
                    MQTTClient.QOS1)
  

                

class Sensor(MQTTAgent):
    """Sensor Agent

    This agent is used to handle publications to the sensor topic and
    any publications it makes.
    """
    SENSOR_TOPIC_PREFIX = "track/sensor"
   

    SENSOR_PAYLOAD = {DCCBlkDet.BLK_EMPTY:"INACTIVE",
                       DCCBlkDet.BLK_OCC:"ACTIVE",
                       DCCBlkDet.BLK_NPOW:"INACTIVE"}
    """Sensor payload look up
    
    Dictionary to translate internal status to reported status"""
    

    def __init__(self, sensor):
        """Construct the Sensor agent
        
        Create object variables and initialise the base Agent class topic and QoS"""
        self._sensor = sensor 
        self._name = sensor.name
        super().__init__(f'{Sensor.SENSOR_TOPIC_PREFIX}/{self._name}/set', MQTTClient.QOS1)

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
        pass

    async def _pub_check(self):
        """ Publication check
        
            Check to see if block state has changed and publish it.
        
            This coroutine runs forever.
        """
        while True:
            await self._sensor.wait_for_flag()

            # Get the new sensor state and publish it
            await self._client.publish(
                f'{Sensor.SENSOR_TOPIC_PREFIX}/{self._name}/event',
                Sensor.SENSOR_PAYLOAD[self._sensor.sensor_state],
                False,
                MQTTClient.QOS1)

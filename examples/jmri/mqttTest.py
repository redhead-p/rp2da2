""" Jython RailCom import script

This script is for use with JMRI to import RailCom Channel 1 and 2 information
using MQTT
"""

import jmri
import json

# Find the MQTT Adapter
mqttAdapter = jmri.InstanceManager.getDefault(jmri.jmrix.mqtt.MqttSystemConnectionMemo).getMqttAdapter()
rc_manager = jmri.InstanceManager.getDefault(jmri.RailComManager)

# RailCom listener class
class RcMqttListener(jmri.jmrix.mqtt.MqttEventListener) :
    def notifyMqttMessage(self, topic, payload):
        topic_list = topic.split('/')
        if topic_list[1] == 'lcl':
            self.handle_local(topic_list[2:], payload)
        elif topic_list[1] == 'gbl':
            self.handle_global(topic_list[2:], payload)

    def handle_local(self, topic_list, payload):
        """Handle RailCom local messages  
        
        """
        try:
            address, orientation = payload.split(' ')
        except ValueError:
            # temporary trap allow script reruns!
            '''if powermanager.getPower() != 2:
                print("bye")
                mqttAdapter.unsubscribeall(self)
                del self
                return'''
            address = None        
        reporter_no = topic_list[-1]
        reporter = reporters.provideReporter(reporter_no)
        reporter.setReport(payload)
        if address is None:
            return
        # there was a dcc address
        rc_id = rc_manager.provideIdTag("RD" + address)
        rc_id.setWhereLastSeen(reporter)
        rc_id.setOrientation(rc_id.Orientation.EAST if orientation == '1'
                            else rc_id.Orientation.WEST)

    def handle_global(self, topic_list, payload):
        """ Handle RailCom Global messages
        """
        address = topic_list[0]
        rc_id = rc_manager.provideIdTag("RD" + address)
        try:
            msg_dict = json.loads(payload)
        except ValueError:
            # not valid json
            return
        for key, value in msg_dict.items():
            if key == 'SPEED':
                rc_id.setActualSpeed(int(value))
                continue
            if key == 'TRACK_VOLTS':
                # nowhere to put this yet
                continue
            if key == "DIRECTION":
                rc_id.setDirection(rc_id.Direction.FORWARD if (value & 1) == 1
                            else rc_id.Direction.BACKWARD)
                # nowhere to put other bit significant items
                continue
            if key == "TEMP":
                rc_id.setActualTemperature(int(value))
                continue
            if key == "RECEP_STATS":
                rc_id.setQoS(rc_id.QoS.GOOD if int(value) <= 15
                             else rc_id.QoS.POOR)  

# register a topic
topic = "rcom/#"
mqttAdapter.subscribe(topic, RcMqttListener())

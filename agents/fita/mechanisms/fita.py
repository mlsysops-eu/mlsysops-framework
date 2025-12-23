#   Copyright (c) 2025. MLSysOps Consortium
#   #
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#   #
#       http://www.apache.org/licenses/LICENSE-2.0
#   #
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#  #
#  #

import os
import asyncio
import json
import traceback
import uuid
from asyncio import CancelledError
from dataclasses import dataclass, field
from typing import Dict

from nextgengw_mqtt_bridge import Mqtt_Bridge
from paho.mqtt.packettypes import PacketTypes
import paho.mqtt.client as mqtt
import mlstelemetry
# MQTT broker information
mqtt_broker_address = os.getenv('MQTT_IP', 'mqtt-broker.fita.svc.cluster.local')
mqtt_broker_port = int(os.getenv('MQTT_PORT','1883'))
node_id = os.getenv('NODE_ID',"b1_node1")
# Extract the trailing bx_nodek part from NODE_ID values like NODENAME-bx_nodek
# Fallback to the whole node_id if the pattern is not present.
try:
    # Split on the last hyphen and take the suffix
    bx_suffix = node_id.rsplit("-", 1)[-1]
except Exception as e:
    # In case of unexpected issues, keep original
    bx_suffix = node_id

# Use bx_suffix wherever the short node identifier is needed
node_id = bx_suffix

telemetry_config_list = os.getenv('TELEMETRY_ENDPOINTS',f"{node_id}/Temperature/0/Property/Sensor_Value")

queues = {"inbound": None, "outbound": None}

mlsTelemetry = mlstelemetry.MLSTelemetry("fita", "fita_mechanism")

def test_msg(client, userdata, msg):
    print(f"Binaryappdata msg: {msg.payload}")


class FitaMechanism:

    state: Dict = field(default_factory=dict)
    inbound_queue = None
    outbound_queue = None
    state = None
    fita_proxy_plans = {}
    mqtt_bridge = None

    def __init__(self, mlsysops_inbound_queue=None, mlsysops_outbound_queue=None, agent_state=None):
        self.inbound_queue = mlsysops_inbound_queue
        self.outbound_queue = mlsysops_outbound_queue
        self.loop = asyncio.get_running_loop()  # inside async context

        self.state = {"applications": {}, "nodes": {}, "submittedPlans": {}}

        self.mqtt_bridge = Mqtt_Bridge(mqtt_broker_address, mqtt_broker_port, node_id)

        print(f"Initializing FITA mechanism of node {node_id} {mqtt_broker_address} : {mqtt_broker_port}")

        self.mqtt_bridge.start(self.fita_on_mqtt_connect)

        self.mqtt_bridge.publish(f"{node_id}/BinaryAppDataContainer/0/Property/Data", '{"operation":"START_OBSERVE"}')
        self.mqtt_bridge.subscribe(f"{node_id}/BinaryAppDataContainer/0/Property/Data", test_msg)


    def fita_on_telemetry_message(self, client, userdata, msg):
        print(f"Telemetry message arrived: {msg.payload}")

        payload = json.loads(msg.payload)

        if "operation" in payload.keys():
            return
        try:
            telemetry_endpoints = telemetry_config_list.split(";")
            for endpoint in telemetry_endpoints:
                if endpoint.replace("/Property","") in msg.topic:

                    keys = endpoint.split("/") #0 node id, 1 object name, 2 object instance, 3 ignore, 4 property name
                    value = payload[keys[0]]["sdfObject"][keys[1]][int(keys[2])]["sdfProperty"][keys[4]]

                    #Send telemetry to mlsysops agent
                    telemetry_event = {"event":"TELEMETRY_EVENT","endpoint":endpoint, "value":value}
                    # {node_id}_{object_name}_{object_instance}_{property_name}
                    telemetry_key = endpoint.replace("/","_")
                    # TODO : the value format might vary
                    for key,extracted_value in value.items():
                        if extracted_value is None or extracted_value == "":
                            continue
                        print(f"Sending telemetry {telemetry_key}: {key} : {extracted_value}")
                        mlsTelemetry.pushMetric(f"{telemetry_key.replace(f'{node_id}_','')}",
                                                "gauge",
                                                float(extracted_value),
                                                attributes={"fita_node_id": node_id})
                    # self.loop.call_soon_threadsafe(self.outbound_queue.put_nowait, telemetry_event)
        except Exception as e:
            print(e)
            print(traceback.format_exc())


    # def fita_on_control_knob_message(self, client, userdata, msg):
    #     try:
    #         print(f"Binary message arrived: {msg.payload}")

    #         payload_json = json.loads(msg.payload)
    #         operation = bytearray.fromhex(payload_json[node_id]["sdfObject"]["BinaryAppDataContainer"][0]["sdfProperty"]["Data"]["0"]).decode()
    #         print(f"Operation: {operation}")

    #         #CHECK WHAT LAST OPERATION WAS
    #         if operation == "set\0":
    #             #Report event
    #             control_knob_event = {}
    #             self.outbound_queue.put(control_knob_event)
    #     except Exception as e:
    #         logger.exception(e)    

    # Callback function for when the client receives a CONNACK response from the broker
    def fita_on_mqtt_connect(self, client, userdata, flags, rc, properties):
        try:
            if rc == 0:
                print("Connected to MQTT broker")

                #Subscribe control knob object, not necessary if we don't care about success of action
                #self.mqtt_bridge.subscribe(f"{node_id}/BinaryAppDataContainer/0/Data", self.fita_on_control_knob_message)
                #self.mqtt_bridge.publish(f"{node_id}/BinaryAppDataContainer/0/Property/Data", '{"operation":"START_OBSERVE"}')

                #Parse Telemetry Configuration
                telemetry_endpoints = telemetry_config_list.split(";")
                for endpoint in telemetry_endpoints:
                    print(endpoint)
                    self.mqtt_bridge.publish(endpoint, '{"operation":"START_OBSERVE"}')
                    self.mqtt_bridge.subscribe(endpoint.replace("/Property",""), self.fita_on_telemetry_message) #.replace because nextgen has different path due to a bug
                    self.mqtt_bridge.subscribe(endpoint, self.fita_on_telemetry_message) #.replace because nextgen has different path due to a bug
            else:
                print("Connection failed with result code " + str(rc))
        except BaseException as e:
            print(e)
            print(traceback.format_exc())


fita_mechanism_instance = None


def initialize(inbound_queue=None, outbound_queue=None, agent_state=None):
    global fita_mechanism_instance

    print("Initializing fita mechanism")

    queues["inbound"] = inbound_queue
    queues["outbound"] = outbound_queue

    fita_mechanism_instance = FitaMechanism(inbound_queue, outbound_queue, agent_state)


async def apply(plan):
    global fita_mechanism_instance

    print('Received from MLSysOps queue msg: %s', plan)
    event = plan.get("event", None)
    data = plan.get("payload", None)

    if event is None or data is None:
        print('Ignoring message: One of event/data is missing.')
        return False

    #Detect whatever event type = control knob action
    if event == "CONTROL_KNOB_EVENT":

        response_topic = str(uuid.uuid4().hex)
        fita_mechanism_instance.state['submittedPlans'][response_topic] = \
            {"planid": plan['plan_id'], "status": "PENDING"}
        publish_property = mqtt.Properties(PacketTypes.PUBLISH)
        publish_property.ResponseTopic = response_topic

        if data["action"] == "SET":
            inner_data = {
                "sdfProperty":{
                    "Data":{
                        "0":f'mlsysops knobs set {data["control_knob"]} {data["value"]}'
                    }
                },
                "sdfAction":{},
                "sdfEvent": {}
            }
            payload = {
                "operation": "POST",
                "data": json.dumps(inner_data)
            }

            #Publish command to set control knob value
            fita_mechanism_instance.mqtt_bridge.publish(
                f"{node_id}/BinaryAppDataContainer/0", 
                json.dumps(payload),
                properties=publish_property,
            )

            return True

    return False


def get_state():
    global fita_mechanism_instance
    if fita_mechanism_instance is not None:
        return fita_mechanism_instance.state
    else:
        return {}


def get_options():
    global fita_mechanism_instance
    return {}
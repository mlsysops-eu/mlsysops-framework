#  Copyright (c) 2025. MLSysOps Consortium
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import asyncio

import mlsysops
from mlsysops.application import MLSApplication
from mlsysops.agent import MLSAgent

from mlsysops.logger_util import logger
import multiprocessing
import fluidity.controller as fluidity_controller
import queue
import copy
from mlsysops.events import MessageEvents

class MLSClusterAgent(MLSAgent):

    def __init__(self):
        super().__init__()
        # Application
        self.active_applications = {}  # Dictionary to track active MLSApplications
        self.fluidity_inbound_queue = asyncio.Queue()
        self.fluidity_outbound_queue = asyncio.Queue()
         # Thread-safe queue
        self.threadsafe_queue = queue.Queue()
        parent_conn, child_conn = multiprocessing.Pipe()
        self.parent_conn = parent_conn
        self.child_conn = child_conn
        self.state.agent = self


    async def run(self):
        """
        Main process of the MLSAgent.
        """
        await super().run()
        logger.info("Starting MLSAgent process...")

        # Start the message queue listener task
        message_queue_task = asyncio.create_task(self.message_queue_listener())
        self.running_tasks.append(message_queue_task)

        # Start fluidity main task
        # TODO DELETE, it is mechanism
        # asyncio.create_task(fluidity_controller.main(outbound_queue=self.fluidity_inbound_queue,inbound_queue=self.fluidity_outbound_queue))

        # start fluidity message queue listener
        fluidity_listener = asyncio.create_task(self.fluidity_message_listener())
        self.running_tasks.append(fluidity_listener)

        await asyncio.gather(*self.running_tasks)

    async def message_queue_listener(self):
        """
        Task to listen for messages from the message queue and act upon them.
        """
        print("MLSAGENT:::: Starting Message Queue Listener...")
        while True:
            try:
                # Wait for a message from the queue
                message = await self.message_queue.get()
                # Extract event type and application details from the message
                event = message.get("event")  # Expected event field
                #print(event)
                #data = message.get("data")  # Additional application-specific data
                data = message.get("payload")
                #node = data.get("hostname")
                # Act upon the event type
                logger.debug(f"Received message from spade msg queue of event {event}")

                match event:
                    case mlsysops.events.MessageEvents.COMPONENT_PLACED.value:
                        # a reconfiguration request received from node agent
                        logger.debug(f"Sending to fluidity: {data}")
                        await self.parent_conn.send(data)
                        return
                    case mlsysops.events.MessageEvents.OTEL_DEPLOY.value:
                        logger.debug(f"Received OTEL_DEPLOY msg from spade")
                        await self.telemetry_controller.remote_apply_otel_configuration(data['node'],data['otel_config'])
                    case mlsysops.events.MessageEvents.OTEL_REMOVE.value:
                        logger.debug(f"Received OTEL_REMOVE msg from spade")
                        self.telemetry_controller.remove_otel_configuration(data['node'])
                    case mlsysops.events.MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMIT.value:
                        logger.debug(f"Received {mlsysops.events.MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMIT.value} from spade")
                        await self.state.assets["fluidity"].send_message({
                            "event": mlsysops.events.MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMIT.value,
                            "payload": data
                        })
                    case mlsysops.events.MessageEvents.MESSAGE_TO_FLUIDITY.value:
                        # Make it passthrough to fluidity
                        await self.mechanisms_controller.queues['fluidity']['outbound'].put({
                            "event": event,
                            "payload": data
                        })
                    case _:
                        print(f"Unhandled event type: {event}")
                print("Going to sleep for 1 second...")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"message_queue_listener: Error processing message: {e}")
                print("Going to sleep for 1 second...")
                await asyncio.sleep(1)

    async def fluidity_message_listener(self):
        logger.debug(f"MLSAGENT::::  Starting fluidity message listener.... ")
        while True:
            try:
                msg = await self.mechanisms_controller.queues['fluidity']['inbound'].get()
                logger.debug('====================Received from fluidity ======================')
                event = msg.get("event")  # Expected event field
                logger.debug(f'Event {event}')
                data = msg.get("payload")  # Additional application-specific data
                match event:
                    case MessageEvents.APP_CREATED.value:
                        logger.debug(f"Received APP_CREATED msg from fluidity")
                        await self.application_controller.on_application_received(data)
                        await self.policy_controller.start_application_policies(data['name'])
                    case MessageEvents.APP_DELETED.value:
                        logger.debug(f"Application was removed {self.state.applications[data].app_desc}")
                        nodes_to_send = []
                        # for comp_spec in self.state.applications[data].component_spec:
                        await self.application_controller.on_application_terminated(data)
                        await self.policy_controller.delete_application_policies(data)
                        # send messages to nodes
                        logger.debug(f"=================== {data}")
                        # for node in data['nodes']:
                        #     await self.send_message_to_node(node, event, data['name'])
                    case MessageEvents.APP_UPDATED.value:
                        logger.debug(f"Application was updated")
                        await self.application_controller.on_application_updated(data)
                    case MessageEvents.COMPONENT_PLACED.value:
                        logger.debug(f"Application component placed")

                        # Update internal structure
                        await self.application_controller.on_application_updated(data)
                        app_name = data['name']
                        comp_dict = data['comp_dict']
                        
                        for comp_name in comp_dict:
                            #logger.info(f'comp_name {comp_name}')
                            send_msg = {
                                'name': app_name,
                                'metrics' : comp_dict[comp_name]['qos_metrics'],
                                'spec': None
                            }
                            component_list = {}
                            for comp_spec in comp_dict[comp_name]['specs']:
                                node = comp_spec['spec']['nodeName']
                                if node not in component_list.keys():
                                    # create a new
                                    component_list[node] = []
                                component_list[node].append(copy.deepcopy(comp_spec))

                            # send the appropriate message in every node
                            for node_name, comp_specs in component_list.items():
                                send_msg['spec'] = {
                                    "components": comp_specs

                                }
                                logger.debug(f'Going to send {send_msg} to node {node}')
                                await self.send_message_to_node(node_name, event, send_msg)
                    case MessageEvents.COMPONENT_REMOVED.value:
                        # Not used
                        logger.debug(f"Application component removed")
                    case _:
                        logger.debug(f"Received msg from fluidity: {data}")
                        node = data['hostname']
                        await self.send_message_to_node(node,event,data)

            except asyncio.CancelledError:
                logger.debug(f"fluidity_message_listener: CancelledError")
                break
            except Exception as e:
                logger.error(f"fluidity_message_listener: Error processing msg: {e}")
                await asyncio.sleep(1)
        print(f"MLSAGENT::::  stopping fluidity message listener.... ")
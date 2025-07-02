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
import json
import traceback
from copy import deepcopy

import mlsysops
from mlsysops.agent import MLSAgent

from mlsysops.logger_util import logger
import copy
from mlsysops.events import MessageEvents

class MLSClusterAgent(MLSAgent):

    def __init__(self):
        super().__init__()

        self.state.agent = self

        self.nodes_state = {}

    async def run(self):
        """
        Main process of the MLSAgent.
        """
        await super().run()
        logger.info("Starting MLSAgent process...")

        # Start the message queue listener task
        message_queue_task = asyncio.create_task(self.message_queue_listener())
        self.running_tasks.append(message_queue_task)

        # start fluidity message queue listener
        fluidity_listener = asyncio.create_task(self.fluidity_message_listener())
        self.running_tasks.append(fluidity_listener)

        await asyncio.gather(*self.running_tasks)

    async def stop(self):
        await super().stop()

        for running_task in self.running_tasks:
            running_task.cancel()
        logger.debug("Finished cleaning up MLSClusterAgent resources...")

    async def message_queue_listener(self):
        """
        Waits for and processes messages from a message queue, handling different event types by executing corresponding
        tasks such as delegating telemetry configurations, deploying/removing components, or syncing node states.

        This method uses asynchronous operations to handle message processing and ensures all events are logged appropriately.
        It plays a critical role in managing communication and operations between different components of the system.

        Parameters
        ----------
        self : object
            Instance of the class that manages this method. May include attributes such as message queues, telemetry controllers,
            mechanisms controllers, and node states for handling functionality defined within this method.

        Returns
        -------
        None
            This method does not return any value but processes incoming messages and performs respective actions asynchronously.

        Raises
        ------
        Exception
            Catches and logs any exception that occurs during the processing of messages from the queue.
        """
        logger.info("Started Message Queue Listener...")
        while True:
            try:
                # Wait for a message from the queue
                message = await self.message_queue.get()

                # Extract event type and application details from the message
                event = message.get("event")
                data = message.get("payload")

                # Act upon the event type
                logger.debug(f"Received message from spade msg queue of event {event}")
                logger.debug(f"Payload: {message}")

                match event:
                    case mlsysops.events.MessageEvents.COMPONENT_PLACED.value:
                        logger.debug(f"Sending to fluidity: {data}")
                        return
                    case mlsysops.events.MessageEvents.OTEL_DEPLOY.value:
                        logger.debug(f"Received OTEL_DEPLOY msg from spade")
                        await self.telemetry_controller.remote_apply_otel_configuration(data['node'],data['otel_config'], data['interval'])
                    case mlsysops.events.MessageEvents.OTEL_REMOVE.value:
                        logger.debug(f"Received OTEL_REMOVE msg from spade")
                        self.telemetry_controller.remove_otel_configuration(data['node'])
                    case mlsysops.events.MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMITTED.value:
                        logger.debug(f"Received {mlsysops.events.MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMITTED.value} from spade")
                        await self.state.active_mechanisms["fluidity"]['module'].send_message({
                            "event": mlsysops.events.MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMITTED.value,
                            "payload": data
                        })

                    case mlsysops.events.MessageEvents.MESSAGE_TO_FLUIDITY.value:
                        await self.mechanisms_controller.queues['fluidity']['outbound'].put({
                            "event": event,
                            "payload": data
                        })
                    case mlsysops.events.MessageEvents.NODE_EXPORTER_DEPLOY.value:
                        logger.debug(f"Received node exporter deploy msg from node")
                        await self.telemetry_controller.remote_apply_node_exporter(data)
                    case mlsysops.events.MessageEvents.NODE_EXPORTER_REMOVE.value:
                        logger.debug(f"Received node exporter remove msg from node")
                        self.telemetry_controller.remote_remove_node_exporter_pod(data['node'])
                    case mlsysops.events.MessageEvents.NODE_STATE_SYNC.value:
                        # logger.debug(f"Going to send {self.nodes_state[data['node']]} to node {data['node']}")
                        await self.send_message_to_node(
                            data['node'],
                            MessageEvents.NODE_STATE_SYNC.value,
                            self.nodes_state[data['node']])
                    case _:
                        logger.error(f"Unhandled event type: {event}")

            except Exception as e:
                logger.error(f"Error processing message in message_queue_listener: {e}")
        logger.debug("Started Message Queue Listener...")

    async def fluidity_message_listener(self):
        """
        An asynchronous function that listens for incoming fluidity messages and handles events accordingly. This function operates
        continuously, processing messages from the inbound queue of the fluidity mechanisms controller. It performs operations such as
        managing applications, updating nodes and components, and coordinating responses to various event types.

        Attributes:
            mechanisms_controller: Reference to the mechanisms controller that manages the message queues.
            application_controller: Maintains the state and behavior of applications handled by the system.
            policy_controller: Handles policies associated with applications and their execution.
            nodes_state: Dictionary containing the state information of nodes in the system.

        Raises:
            Exceptions based on any failures during asynchronous message handling, specific to implementation.
        """
        logger.debug(f"Starting fluidity message listener.... ")
        while True:
            try:
                msg = await self.mechanisms_controller.queues['fluidity']['inbound'].get()

                if not msg:
                    continue

                event = msg.get("event")
                data = msg.get("payload")

                match event:
                    case MessageEvents.APP_CREATED.value:
                        logger.debug(f"Received APP_CREATED msg from fluidity")
                        await self.application_controller.on_application_received(data)
                        await self.policy_controller.start_application_policies(data['name'])
                    case MessageEvents.APP_DELETED.value:
                        app_name = data['name']
                        logger.debug(f"Application was removed {app_name}")

                        await self.application_controller.on_application_terminated(app_name)
                        await self.policy_controller.delete_application_policies(app_name)

                        # send messages to nodes
                        for node_name, node_state in self.nodes_state.items():
                            if app_name in node_state.keys():
                                for component_in_node in self.nodes_state[node_name][app_name]['components'].keys():
                                    msg_to_send = {
                                            'name': app_name,
                                            'component_name': component_in_node
                                    }
                                    await self.send_message_to_node(node_name, MessageEvents.COMPONENT_REMOVED.value, msg_to_send)
                                del self.nodes_state[node_name][app_name]
                    case MessageEvents.APP_UPDATED.value:
                        logger.debug(f"Application was updated")
                        await self.application_controller.on_application_updated(data)
                    case MessageEvents.COMPONENT_PLACED.value: # DEPRACATED
                        # logger.debug(f"Application component placed")
                        # logger.debug(f"Data: {data}")
                        # Update internal structure
                        await self.application_controller.on_application_updated(data)
                        app_name = data['name']
                        comp_dict = data['comp_dict']
                        qos_metrics = data.get('qos_metrics', None)
                        for comp_name in comp_dict:
                            #logger.info(f'comp_name {comp_name}')
                            send_msg = {
                                'name': app_name,
                                'metrics' : qos_metrics,
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
                    case MessageEvents.KUBERNETES_NODE_ADDED.value:
                        logger.debug(f"Kubernetes node event {event}")
                    case MessageEvents.KUBERNETES_NODE_MODIFIED.value:
                        logger.debug(f"Kubernetes node event {event}")
                    case MessageEvents.KUBERNETES_NODE_REMOVED.value:
                        logger.debug(f"Kubernetes node event {event}")
                    case MessageEvents.CLUSTER_SYSTEM_DESCRIPTION_SUBMITTED.value:
                        logger.debug(f"Cluster description event {event}")
                    case MessageEvents.CLUSTER_SYSTEM_DESCRIPTION_UPDATED.value:
                        logger.debug(f"Cluster description event {event}")
                    case MessageEvents.CLUSTER_SYSTEM_DESCRIPTION_REMOVED.value:
                        logger.debug(f"Cluster description event {event}")
                    case MessageEvents.POD_ADDED.value:
                        logger.debug(f"Pod event {event}")
                    case MessageEvents.POD_MODIFIED.value:
                        logger.debug(f"Pod event {event}")
                    case MessageEvents.POD_DELETED.value:
                        logger.debug(f"Pod event {event}")
                    case MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMITTED.value:
                        logger.debug(f"Node description event {event}")
                    case MessageEvents.NODE_SYSTEM_DESCRIPTION_UPDATED.value:
                        logger.debug(f"Node description event {event}")
                    case MessageEvents.NODE_SYSTEM_DESCRIPTION_REMOVED.value:
                        logger.debug(f"Node description event {event}")
                    case MessageEvents.PLAN_EXECUTED.value:
                        logger.debug(f"Plan executed event {event}")
                        update_status = await self.update_plan_status(data['plan_uid'],"fluidity",  data['status'])
                        logger.debug(f"update_status {update_status}")
                        if not update_status:
                            logger.debug(f"Skipping from cluster :{data['plan_uid']} status:{data['status']}")
                            continue # this task is not present in this level

                        logger.debug(f"Plan executed event received id:{data['plan_uid']} status:{data['status']}")
                        logger.test(f"|1| Plan executed event received planuid:{data['plan_uid']} status:{data['status']}")

                        comp_dict = data['comp_dict']

                        if not comp_dict:
                            logger.error('Plan failed, comp dict is empty.')
                            continue

                        application_name = data['name']

                        # Check if plan kind - change_comp spec, do not change component dict
                        task_object = self.state.get_task_log(data['plan_uid'])
                        plan_json = json.loads(task_object['plan'])
                        del plan_json['fluidity']['deployment_plan']['initial_plan']
                        logger.debug(f"task_object {task_object}")
                        for component_name_in_plan, component_action_array in plan_json['fluidity']['deployment_plan'].items():
                            for component_action in component_action_array:
                                logger.debug(f"component {component_name_in_plan} action {component_action}")
                                if component_action['action'] in ['change_spec']:
                                    # update spec
                                    node_name_spec_changed = component_action.get('host',None)
                                    if data['status']: # Success
                                        logger.debug(f"Pod {component_name_in_plan} component spec changed on node {node_name_spec_changed}")
                                        for pod_spec in comp_dict[component_name_in_plan]['specs']: # TODO probably we can find better way to get pod_spec
                                            self.nodes_state[node_name_spec_changed][application_name]['components'][component_name_in_plan] = pod_spec

                                        # Remove component from application description that are not placed on the specific node
                                        active_component_names = list(
                                            self.nodes_state[node_name_spec_changed][application_name][
                                                'components'].keys())

                                        # Remove components from data['spec']['components'] if their name is not in component_names
                                        application_description_spec = deepcopy(data['spec'])
                                        application_description_spec['components'] = [
                                            component for component in application_description_spec['components']
                                            if component['metadata']['name'] in active_component_names
                                        ]

                                        ## send a message to each node
                                        send_msg = {
                                            'name': application_name,
                                            'component_name': component_name_in_plan,
                                            'spec': application_description_spec,
                                            'pod_spec': self.nodes_state[node_name_spec_changed][application_name]['components'][component_name_in_plan]
                                        }

                                        # send the appropriate message in every node
                                        logger.debug(f'Going to send {event} to node {node_name_spec_changed}')
                                        await self.send_message_to_node(
                                            node_name_spec_changed,
                                            MessageEvents.COMPONENT_UPDATED.value,
                                            send_msg)

                                    # Failed do nothing
                                elif component_action['action'] in ['move', 'deploy', 'remove']:
                                    for component_name, component_object in comp_dict.items():
                                        for pod_name, pod_component in component_object['specs'].items():
                                            if pod_component['event'] == MessageEvents.COMPONENT_REMOVED.value:
                                                logger.debug(f"Pod {pod_name} component {component_name}  removed skipping")
                                                node_name_removed = pod_component.get('hostname',{})
                                                send_msg = {
                                                    'name': application_name,
                                                    'component_name': component_name
                                                }
                                                # send the appropriate message in every node
                                                logger.debug(f'Move plan. Sending {component_name} removal to node {node_name_removed}')
                                                await self.send_message_to_node(
                                                    node_name_removed,
                                                    MessageEvents.COMPONENT_REMOVED.value,
                                                    send_msg)

                                                # remove from local state
                                                del self.nodes_state[node_name_removed][application_name]['components'][component_name]

                                                continue
                                            node_name_placed = pod_component.get('pod_spec',{}).get('pod_spec',{}).get('spec',{}).get('nodeName',{})
                                            logger.debug(f"Pod {pod_name} component {component_name}  placed on node {node_name_placed}")

                                            # put in local state
                                            self.nodes_state.setdefault(node_name_placed, {})
                                            self.nodes_state[node_name_placed].setdefault(application_name, {})
                                            self.nodes_state[node_name_placed][application_name]['name'] = application_name
                                            self.nodes_state[node_name_placed][application_name].setdefault('components', {})
                                            self.nodes_state[node_name_placed][application_name]['components'][component_name] = pod_component['pod_spec']
                                            self.nodes_state[node_name_placed][application_name]['spec'] = data['spec']

                                            # Remove component from application description that are not placed on the specific node
                                            active_component_names = list(self.nodes_state[node_name_placed][application_name]['components'].keys())

                                            # Remove components from data['spec']['components'] if their name is not in component_names
                                            application_description_spec = deepcopy(data['spec'])
                                            application_description_spec['components'] = [
                                                component for component in application_description_spec['components']
                                                if component['metadata']['name'] in active_component_names
                                            ]

                                            ## send a message to each node
                                            send_msg = {
                                                'name': application_name,
                                                'component_name': component_name,
                                                'spec': application_description_spec,
                                                'pod_spec': pod_component.get('pod_spec',{}).get('comp_sec',{})
                                            }

                                            # send the appropriate message in every node
                                            logger.debug(f'Going to send {event} to node {node_name_placed}')
                                            await self.send_message_to_node(
                                                node_name_placed,
                                                MessageEvents.COMPONENT_PLACED.value,
                                                send_msg)
                    case MessageEvents.MESSAGE_TO_FLUIDITY_PROXY.value:
                        # forward to node
                        logger.debug(f"Received {event} from fluidity proxy to node {msg['node']}")
                        await self.send_message_to_node(msg['node'],event,data)
                    case _:
                        logger.debug(f"Unknown event: Received payload from fluidity: {data}")
                        if data and 'hostname' in data:
                            node = data['hostname']
                            await self.send_message_to_node(node,event,data)

            except asyncio.CancelledError:
                logger.info(f"Stopping fluidity message listener.... ")
                break
            except Exception as e:
                logger.error(f"fluidity_message_listener: Error processing msg: {e}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(1)
        logger.debug(f"MLSAGENT::::  stopping fluidity message listener.... ")
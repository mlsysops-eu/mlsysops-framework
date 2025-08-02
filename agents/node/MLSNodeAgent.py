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
import traceback

from mlsysops.agent import MLSAgent
from mlsysops.events import MessageEvents
from mlsysops.logger_util import logger


class MLSNodeAgent(MLSAgent):

    def __init__(self):
        # Initialize base MLS agent class
        logger.debug("In INIT OF NODE AGENT")
        super().__init__()

        # { 'app_name' : { "components" : [component_name] } }
        self.active_application = {}


    async def run(self):
        """
        Main process of the MLSAgent.
        """
        await super().run()

        logger.info("Starting MLSAgent process...")

        # Start the message queue listener task
        message_queue_task = asyncio.create_task(self.message_queue_listener())
        self.running_tasks.append(message_queue_task)

        # Start fluidity proxy message listener
        # TODO make it optional
        fluidity_proxy_task = asyncio.create_task(self.fluidity_proxy_message_listener())
        self.running_tasks.append(fluidity_proxy_task)

        # sending sync request
        await self.send_message_to_node(self.state.configuration.cluster, MessageEvents.NODE_STATE_SYNC.value, {"node": self.state.configuration.node})

        try:
            results = await asyncio.gather(*self.running_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task raised an exception: {result}")
        except Exception as e:
            logger.error(f"Error in running tasks: {e}")

        logger("MLSAgent stopped.")

    async def message_queue_listener(self):
        """
        Coroutine that listens for and processes messages from a queue. It manages the lifecycle
        of applications and their components, handles telemetry updates, synchronizes node states,
        and forwards specific events to other mechanisms when necessary. The coroutine operates in
        an infinite loop, extracting and reacting to events received from the message queue.

        Raises
        ------
        Exception
            If an error occurs during the processing of a message, the resulting exception is logged
            but not propagated, ensuring continuous operation of the infinite loop.
        """
        logger.info("Starting Message Queue Listener...")
        while True:
            try:
                # Wait for a message from the queue
                message = await self.message_queue.get()

                # Extract event type and application details from the message
                event = message.get("event")  # Expected event field
                data = message.get("payload")  # Additional application-specific data
                logger.debug(f"Received message: {event}")

                # Act upon the event type
                if event == MessageEvents.COMPONENT_PLACED.value:
                    application_object = self.active_application.get(data['name'], None)
                    if application_object is None:
                        self.active_application[data['name']] = {"components" : []}
                        self.active_application[data['name']]['components'].append(data['component_name'])
                        logger.debug(f"Component {data['component_name']} placed in new application {data['name']}")
                        await self.application_controller.on_application_received(data)
                        await self.policy_controller.start_application_policies(data['name'])
                    else:
                        if data['component_name'] not in application_object['components']:
                            application_object['components'].append(data['component_name'])
                            logger.debug(f"Component {data['component_name']} placed in existing application {data['name']}")
                            await self.application_controller.on_application_updated(data)
                elif event == MessageEvents.COMPONENT_UPDATED.value:
                    application_object = self.active_application.get(data['name'], None)
                    if application_object is not None:
                        logger.debug(f"Component {data['component_name']} updated in application {data['name']}")
                        await self.application_controller.on_application_updated(data)

                elif event == MessageEvents.COMPONENT_REMOVED.value:
                    application_object = self.active_application.get(data['name'], None)
                    if application_object is not None:
                        if data['component_name'] in application_object['components']:
                            application_object['components'].remove(data['component_name'])
                            logger.debug(f"Component {data['component_name']} removed from application {data['name']}")
                            await self.application_controller.on_application_updated(data)
                        if len(application_object['components']) == 0:
                            await self.application_controller.on_application_terminated(data['name'])
                            await self.policy_controller.delete_application_policies(data['name'])
                            del self.active_application[data['name']]
                            logger.debug(f"All components of application {data['name']} removed.")
                elif event == MessageEvents.OTEL_NODE_INTERVAL_UPDATE.value:
                    await self.telemetry_controller.add_new_interval(id=self.state.configuration.cluster,new_interval=data[0]['interval'])
                elif event == MessageEvents.NODE_STATE_SYNC.value:
                    logger.debug(f"Received NODE_STATE_SYNC msg from cluster ")
                    for application_name, application_data in data.items():
                        for component_name,_ in application_data['components'].items():
                            application_object = self.active_application.get(application_name, None)

                            if application_object is None:
                                self.active_application[application_name] = {"components": []}
                                self.active_application[application_name]['components'].append(component_name)
                                logger.debug(f"Component {component_name} placed in new application {application_name}")
                                await self.application_controller.on_application_received(application_data)
                                await self.policy_controller.start_application_policies(application_name)
                            else:
                                if component_name not in application_object['components']:
                                    application_object['components'].append(component_name)
                                    logger.debug(
                                        f"Component {component_name} placed in existing application {application_name}")
                                    await self.application_controller.on_application_updated(application_data)
                elif event == MessageEvents.MESSAGE_TO_FLUIDITY_PROXY.value:
                    # forward to fluidity proxy
                    logger.debug(f"Received message to fluidity proxy mechanism")
                    if self.mechanisms_controller.is_mechanism_enabled("fluidity_proxy"):
                        await self.mechanisms_controller.queues['fluidity_proxy']['outbound'].put(message)
                else:
                    logger.error(f"Unhandled event type: {event}")
                    logger.error(traceback.format_exc())

            except Exception as e:
                logger.error(f"Error processing message: {traceback.format_exc()}")

    async def fluidity_proxy_message_listener(self):
        """
        Handles incoming messages from the fluidity proxy message queue, processes the
        received events, and executes corresponding actions based on event types.

        Raises
        ------
        asyncio.CancelledError
            Raised when the task is cancelled while awaiting.
        Exception
            General exception raised if an unexpected error occurs during message
            processing.

        Returns
        -------
        None
        """
        logger.debug(f"MLSAGENT Node:::: Starting fluidity proxy message listener.... ")
        while True:
            try:
                msg = await self.mechanisms_controller.queues['fluidity_proxy']['inbound'].get()

                event = msg.get("event")
                data = msg.get("payload")
                logger.debug(f"Received msg from fluidity_proxy event { event }: { data }")

                match event:
                    case MessageEvents.MESSAGE_TO_FLUIDITY.value:
                        # Send the message to cluster fluidity
                        data['node'] = self.state.configuration.node
                        await self.send_message_to_node(self.state.configuration.cluster, event, data)
                        continue
                    case MessageEvents.PLAN_EXECUTED.value:
                        await self.update_plan_status(data['plan_uid'], "fluidity_proxy", data['status'])
                    case _:
                        logger.error(f"Received msg from fluidity proxy with wrong event")

            except asyncio.CancelledError:
                logger.debug(f"fluidityproxy_message_listener: CancelledError")
                break
            except Exception as e:
                logger.error(f"fluidityproxy_message_listener: Error processing msg: {e}")
                await asyncio.sleep(1)
        logger(f"MLSAGENT::::  stopping fluidity message listener.... ")

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
#

import asyncio

from mlsysops.data.task_log import Status
from mlsysops.events import MessageEvents
from mlsysops.controllers.application import ApplicationController
from mlsysops.controllers.configuration import ConfigurationController
from mlsysops.controllers.policy import PolicyController
from mlsysops.controllers.telemetry import TelemetryController
from mlsysops.controllers.mechanisms import MechanismsController
from mlsysops.data.state import MLSState
from mlsysops.scheduler import PlanScheduler
from mlsysops.spade.mls_spade import MLSSpade
from mlsysops.tasks.monitor import MonitorTask
from mlsysops.data.monitor import MonitorData

from mlsysops.logger_util import logger


class MLSAgent:

    def __init__(self):
        logger.debug("Initializing agent...")

        self.running_tasks = []

        # Knowledge base
        self.state = MLSState()
        self.state.start_period_log_dump()

        # Monitor task
        self.monitor_data = MonitorData()
        self.monitor_queue = asyncio.Queue()
        self.monitor_task = MonitorTask(self.state, self.monitor_queue, self.monitor_data)
        monitor_async_task = asyncio.create_task(self.monitor_task.run())
        self.running_tasks.append(monitor_async_task)

        # ##------- Controllers --------------##
        logger.debug("Initializing controllers...")

        # Configuration Controller
        self.configuration_controller = ConfigurationController(self.state)

        # Telemetry
        self.telemetry_controller = TelemetryController(self,self.monitor_task, self.state)

        # Policy Controller
        self.policy_controller = PolicyController().init(self.state)
        self.policy_controller.load_policy_modules()

        # Application Controller
        self.application_controller = ApplicationController(self.monitor_task, self.state)

        # Mechanisms Controller
        self.mechanisms_controller = MechanismsController().init(self.state)
        try:
            self.mechanisms_controller.load_mechanisms_modules()
        except Exception as e:
            logger.error(f"Error loading mechanisms: {e}")
            logger.debug(self.state.assets)

        # ##--------- Scheduler --------------#
        logger.debug("Initializing scheduler...")
        self.scheduler = PlanScheduler(self.state)
        scheduler_async_task = asyncio.create_task(self.scheduler.run())
        self.running_tasks.append(scheduler_async_task)

        # ## -------- SPADE ------------------#
        logger.debug("Initializing SPADE...")
        try:
            self.message_queue = asyncio.Queue()
            self.spade_instance = MLSSpade(self.state, self.message_queue)
        except Exception as e:
            logger.error(f"Error initializing SPADE: {e}")

    def __del__(self):
        self.stop()

    async def stop(self):
        """
        Destructor method called when the object is deleted or goes out of scope.
        Cleans up resources like queues, tasks, or objects to ensure no leaks.
        """
        print("Cleaning up MLSAgent resources...")
        # Clean up controllers
        del self.application_controller
        del self.policy_controller
        del self.configuration_controller
        del self.telemetry_controller

        await asyncio.sleep(5)

        # Cancel all running tasks
        for task in self.running_tasks:
            if not task.done() and not task.cancelled():
                task.cancel()
                print(f"Cancelled task: {task}")

        # Cleanup spade agent
        if self.spade_instance:
            await self.spade_instance.stop()

        # Close the monitor queue if it exists
        if not self.monitor_queue.empty():
            try:
                self.monitor_queue = None
                print("Monitor queue cleaned.")

            except Exception as e:
                print(f"Failed to clear monitor queue: {e}")




        # Clean up any knowledge base-related resources
        del self.state

        print("MLSAgent cleanup complete.")

    def __str__(self):
        return f"{self.__class__.__name__} running on hostname: {MLSState.hostname}"


    async def message_queue_listener(self):
        """
        Task to listen for messages from the message queue and act upon them.
        """
        print("Starting default Message Queue Listener...")
        while True:
            try:
                # Wait for a message from the queue (default behavior)
                message = await self.message_queue.get()
                print(f"Received message: {message}")
                # Default handling logic (can be extended in subclasses)
            except Exception as e:
                print(f"Error in message listener: {e}")

    async def send_message_to_node(self, recipient, event, payload):
        """
        Sends a message to a specified recipient node with a designated event and payload.

        Args:
            recipient (str): The identifier of the recipient node to which the message
            is being sent.

            event (str): The specific event type or identifier associated with the
            message to help the recipient define the context of the communication.

            payload (Any): The data or content being sent as part of the message
            communication. The type of the payload can be flexible, determined based
            on application-specific requirements.
        """
        await self.spade_instance.send_message(recipient, event, payload)

    async def update_plan_status(self, plan_uuid, asset, status):
        """
        Update the status of a specific asset in the task log and determine the overall plan status.

        Args:
            plan_uuid: The unique identifier of the plan.
            asset: The asset for which the status is being set.
            status: True or False - the status to assign to the asset.
        """
        # Get the current task log
        task_log = self.state.get_task_log(plan_uuid)

        # Update the specific asset's status
        if asset in task_log["assets"]:
            task_log["assets"][asset] = status  # Set the status for the specific asset

            # Check if all assets are True
            all_assets_status = all(value != "Pending" for value in task_log["assets"].values())

            if all_assets_status:
                # Send updates to the task log
                self.state.update_task_log(plan_uuid, updates={"status": Status.COMPLETED, "assets": task_log["assets"]})

    async def run(self):
        """
        Main process of the MLSAgent.
        """
        # Apply MLS System description
        try:
            if self.state.configuration.continuum_layer == 'cluster':
                logger.debug(f"Applying system description")
                await self.state.assets["fluidity"]["module"].send_message({
                    "event": MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMIT.value,
                    "payload": self.state.configuration.system_description
                })
            if self.state.configuration.continuum_layer == 'node':
                logger.debug(f"Send my {self.state.configuration.node} description to cluster")
                await self.send_message_to_node(
                    self.state.configuration.cluster,
                     MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMIT.value,
                    self.state.configuration.system_description)
        except Exception as e:
            logger.error(f"Error executing command: {e}")

        await self.telemetry_controller.apply_configuration_telemetry()
        await self.telemetry_controller.initialize()
        await self.spade_instance.start(auto_register=True)

        # Start global policies
        self.policy_controller.start_global_policies()
        self.policy_controller.start_policy_directory_monitor()

        return True


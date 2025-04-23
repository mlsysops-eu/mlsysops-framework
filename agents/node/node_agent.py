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

from mlsysops.application import MLSApplication
from mlsysops.agent import MLSAgent
from mlsysops.events import MessageEvents
from mlsysops.logger_util import logger


class MLSNodeAgent(MLSAgent):

    def __init__(self):
        # Initialize base MLS agent class
        super().__init__()

        # Application
        self.active_components = {}  # Dictionary to track active application MLSComponent

    async def run(self):
        """
        Main process of the MLSAgent.
        """
        await super().run()

        logger.info("Starting MLSAgent process...")

        # Start the message queue listener task
        message_queue_task = asyncio.create_task(self.message_queue_listener())
        self.running_tasks.append(message_queue_task)

        try:
            results = await asyncio.gather(*self.running_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task raised an exception: {result}")
        except Exception as e:
            logger.error(f"Error in running tasks: {e}")

        print("MLSAgent stopped.")

    async def message_queue_listener(self):
        """
        Task to listen for messages from the message queue and act upon them.
        """
        logger.info("Starting Message Queue Listener...")
        while True:
            try:
                # Wait for a message from the queue
                message = await self.message_queue.get()
                print(f"Received message: {message}")

                # Extract event type and application details from the message
                event = message.get("event")  # Expected event field
                data = message.get("payload")  # Additional application-specific data
                # Act upon the event type
                if event == MessageEvents.COMPONENT_PLACED.value:
                    await self.application_controller.on_application_received(data)
                if event == MessageEvents.COMPONENT_REMOVED.value:
                    await self.application_controller.on_application_removed(data
                                                                             )
                else:
                    print(f"Unhandled event type: {event}")

            except Exception as e:
                print(f"Error processing message: {e}")


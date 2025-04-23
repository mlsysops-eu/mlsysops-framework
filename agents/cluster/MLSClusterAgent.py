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
import fluidity.cloud.fluidityapp_controller as fluidityapp_controller
import queue


def run_fluidity_main(pipe):
    fluidityapp_controller.main(pipe)

def run_process_event_loop(queue):
    """Starts an asyncio event loop in a separate process."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(fluidityapp_controller.main(queue))

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

    async def non_blocking_join(self, process):
        """Polls the process every 0.5s instead of blocking."""
        while process.is_alive():
            await asyncio.sleep(0.5)  # Non-blocking
        print("Worker process finished.")

    async def run(self):
        """
        Main process of the MLSAgent.
        """
        await super().run()
        logger.info("Starting MLSAgent process...")

        # Start the message queue listener task
        message_queue_task = asyncio.create_task(self.message_queue_listener())
        self.running_tasks.append(message_queue_task)

        # Start process with its own event loop
        process = multiprocessing.Process(target=run_process_event_loop, args=(self.child_conn,))
        process.start()
        #
        # # start fluidity message queue listener
        fluidity_listener = asyncio.create_task(self.fluidity_message_listener())
        self.running_tasks.append(fluidity_listener)

        await asyncio.gather(*self.running_tasks)

        # await self.non_blocking_join(process)


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
                print(f"Received message from spade msg queue of event {event}")

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
                msg = await asyncio.to_thread(self.parent_conn.recv)
                print('==========================================')
                logger.debug(f'Received message from fluidity {msg}')
                print("Sending it to spade")
                #await self.message_queue.put(message_test)
                for entry in msg:
                    event = entry.get("event")  # Expected event field
                    data = entry.get("payload")  # Additional application-specific data
                    node = data.get("hostname")
                    await self.send_message_to_node(node,event,data)
            except Exception as e:
                print(f"fluidity_message_listener: Error processing msg: {e}")
                await asyncio.sleep(1)
        print(f"MLSAGENT::::  stopping fluidity message listener.... ")

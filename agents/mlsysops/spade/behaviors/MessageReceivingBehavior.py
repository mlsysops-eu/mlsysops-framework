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

from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

import json

from ...events import MessageEvents
from ...logger_util import logger


class MessageReceivingBehavior(CyclicBehaviour):

    def __init__(self, message_queue: asyncio.Queue):
        super().__init__()
        self.message_queue = message_queue


    async def run(self):
        msg = await self.receive(timeout=10)  # wait for a message for 10 seconds
        if msg:
            sender = str(msg._sender).split("/")[0]

            # Decode message
            performative = msg.get_metadata("performative")
            event = msg.get_metadata("event")
            thread = msg.thread

            resp = Message(to=sender)
            resp.thread = msg.thread
            logger.debug(f"Received {event} from {sender} of performative {performative}")
            match (performative, event):
                case ("request", MessageEvents.COMPONENT_PLACED.value):
                    logger.debug("Application Component Placed")
                    # Decode payload
                    payload = {
                        "event": event,
                        "payload": json.loads(msg.body)
                    }
                    # inform agent for receiving
                    await self.message_queue.put(payload)
                case ("request", MessageEvents.COMPONENT_REMOVED.value):
                    logger.debug("Application Component Removed")
                    # Decode payload
                    payload = {
                        "event": event,
                        "payload": json.loads(msg.body)
                    }
                    # inform agent for receiving
                    await self.message_queue.put(payload)
                case ("request", MessageEvents.OTEL_DEPLOY.value):
                    logger.debug(f"Received OTEL Create from {sender}")
                    # Decode payload
                    payload = {
                        "event": event,
                        "payload": json.loads(msg.body)
                    }
                    await self.message_queue.put(payload)
                case ("request", MessageEvents.OTEL_REMOVE.value):
                    logger.debug(f"Received OTEL remove from {sender}")
                    # Decode payload
                    payload = {
                        "event": event,
                        "payload": json.loads(msg.body)
                    }
                    await self.message_queue.put(payload)
                case ("request", MessageEvents.NODE_EXPORTER_DEPLOY.value):
                    logger.debug(f"Received {event} from {sender}")
                    payload = {
                        "event": event,
                        "payload": json.loads(msg.body)
                    }
                    await self.message_queue.put(payload)
                case ("request", MessageEvents.NODE_EXPORTER_REMOVE.value):
                    logger.debug(f"Received {event} from {sender}")
                    payload = {
                        "event": event,
                        "payload": json.loads(msg.body)
                    }
                    await self.message_queue.put(payload)
                case ("request", MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMITTED.value):
                    logger.debug(f"Received node sys desc update from {sender}")
                    payload = {
                        "event": event,
                        "payload": json.loads(msg.body)
                    }
                    await self.message_queue.put(payload)
                case ("request", MessageEvents.MESSAGE_TO_FLUIDITY.value):
                    logger.debug(f"Received {event} from {sender}")
                    payload = {
                        "event": event,
                        "payload": json.loads(msg.body)
                    }
                    await self.message_queue.put(payload)
                case _:
                    logger.debug(f"Received unknown event {event} from {sender} - forwarding to MLSAgent")
                    payload = {
                        "event": event,
                        "payload": json.loads(msg.body)
                    }
                    await self.message_queue.put(payload)
        else:
            logger.debug("Did not received any message after 10 seconds")
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

import random
import uuid
from queue import Queue
import spade
import os
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template
from datetime import datetime

from ...logger_util import logger


class Subscribe(CyclicBehaviour):
    def __init__(self, agent_to_subscribe: str):
        super().__init__()

        self.agent_to_subscribe = agent_to_subscribe

    async def run(self):
        logger.debug("Subscription behaviour running")

        msg = Message(to=str(self.agent_to_subscribe))  # Instantiate the message
        msg.set_metadata("performative", "subscribe")  # Set the "inform" FIPA performative
        msg.thread = str(uuid.uuid4())
        msg.body = "Subscribe request "  # Set the message content
        logger.debug(self.agent_to_subscribe)
        logger.debug(msg.thread)
        await self.send(msg)
        # print("Subscription sent!\n")

        response = await self.receive(timeout=10)  # Wait for a response

        if response and response.get_metadata("performative") == "sub_ack":
            logger.info(f"Subscription acknowledged by {response.sender}")
            self.agent.is_subscribed = True
            self.kill()
        else:
            logger.warning("Subscription failed or timed out")


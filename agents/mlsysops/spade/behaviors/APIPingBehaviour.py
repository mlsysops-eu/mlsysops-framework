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
import json
from ...logger_util import logger


class APIPingBehaviour(CyclicBehaviour):
    """
            A behavior that receives messages and sends responses.
            This is used to do the heartbeat for API.
     """

    async def run(self):
        """Continuously receive and respond to messages in a cyclic manner."""
        logger.info("APIPingBehav running")

        # wait for a message for 10 seconds
        msg = await self.receive(timeout=1)
        if msg:
            #print(str(msg._sender).split("/")[0])
            #print(msg.to)
            logger.debug("Ping received with content: {}".format(msg.body))

            # Create a response message
            resp = Message(to=str(msg._sender).split("/")[0])  # Replace with the actual recipient JID
            resp.set_metadata("performative", "ping")  # Set the "inform" FIPA performative
            resp.body = "Response From " + str(msg.to)  # Set the message content
            #print(resp.body)
            # Send the response message
            await self.send(resp)
            #print("Callback message sent!\n")
        else:
            await asyncio.sleep(5)

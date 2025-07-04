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
import traceback

from ...logger_util import logger
from spade.behaviour import OneShotBehaviour
from spade.message import Message
from spade.template import Template

import uuid
import json


class MessageSendingBehavior(OneShotBehaviour):

    def __init__(self, recipient: str, event: str, payload: dict):
        super().__init__()
        self.recipient = recipient
        self.payload = payload
        self.event = event


    async def run(self):
        try:
            msg = Message(to=f"{self.recipient}@{self.agent.state.configuration.domain}")  # Recipient JID
            msg.set_metadata("performative", "request")  # Standard performative
            msg.set_metadata("event", self.event)  # Custom metadata field
            msg.thread = str(uuid.uuid4())

            payload = self.payload

            serialized_payload = json.dumps(payload)

            msg.body = serialized_payload
            await self.send(msg)
        except Exception as e:
            logger.error(f"Error sending message: {traceback.format_exc()}")
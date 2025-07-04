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

from ...logger_util import logger
from ...data.configuration import AgentConfig
from spade.behaviour import PeriodicBehaviour
from spade.message import Message
from spade.template import Template


class HeartbeatBehaviour(PeriodicBehaviour):


    async def run(self):

        logger.debug("Ping behaviour running\n")

        msg = Message(to=self.agent.state.configuration.c_jid)  # Instantiate the message
        msg.set_metadata("performative", "inform")  # Set the "inform" FIPA performative
        msg.body = "Ping"  # Set the message content

        await self.send(msg)
        logger.debug("HB sent!\n")
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

from datetime import datetime

from spade.behaviour import CyclicBehaviour
from spade.message import Message
import json
from ...logger_util import logger


class HBReceiverBehaviour(CyclicBehaviour):
    """ Handles heartbeat pings from node agents and updates last seen time in Redis. """

    def __init__(self, redis_manager):
        super().__init__()
        self.r = redis_manager

    async def run(self):
        logger.debug(f"HBReceiverBehaviour")
        msg = await self.receive(timeout=5)
        if msg and msg.get_metadata("performative") == "clus_hb":
            node_jid = str(msg.sender).split("/")[0]
            now = datetime.now().isoformat()
            self.r.update_dict_value(self.r.redis_dict, node_jid, now)
            self.r.update_dict_value(self.r.redis_agents, node_jid, now)

            logger.debug(f"Ping received from {node_jid}. Updated last seen time in Redis.")

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
from datetime import datetime

from spade.behaviour import CyclicBehaviour
from spade.message import Message
import json
from ...logger_util import logger


class ManageSubscriptionBehaviour(CyclicBehaviour):
    """ Handles node agent subscriptions and stores them in Redis. """
    def __init__(self, redis_manager):
        super().__init__()
        self.r = redis_manager
    async def run(self):
        logger.debug(f"Manage Subscription Behaviour started.")
        msg = await self.receive(timeout=10)
        if msg and msg.get_metadata("performative") == "subscribe":
            cluster_jid = str(msg.sender).split("/")[0]
            now = datetime.now().isoformat()

            existing_entry = self.r.get_dict_value(self.r.redis_dict, cluster_jid)
            if existing_entry:
                logger.debug(f"Cluster {cluster_jid} is re-registering. Updating last seen timestamp.")
            else:
                logger.debug(f"New Cluster {cluster_jid} subscribed.")

            self.r.update_dict_value(self.r.redis_dict, cluster_jid, now)

            response = Message(to=cluster_jid)
            response.set_metadata("performative", "sub_ack")
            response.body = "Subscription successful"

            await self.send(response)
            logger.debug(f" Node {cluster_jid} registered or updated in Redis.")

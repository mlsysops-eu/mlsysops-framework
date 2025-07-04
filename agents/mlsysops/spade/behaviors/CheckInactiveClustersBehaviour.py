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
from spade.message import Message
import json
from ...logger_util import logger
from spade.behaviour import PeriodicBehaviour
from datetime import datetime, timedelta


class CheckInactiveClustersBehaviour(PeriodicBehaviour):
    """ Checks for inactive node agents and removes them from Redis. """

    def __init__(self, redis_manager):
        super().__init__(period=10)
        self.r = redis_manager
        self.timeout = timedelta(seconds=60)

    async def run(self):
        logger.debug(f"CheckInactiveClustersBehaviour")
        now = datetime.now()
        registered_agents = self.r.get_dict("cluster_agents")
        if registered_agents:
            for node_jid, last_seen in registered_agents.items():
                last_seen_time = datetime.fromisoformat(last_seen)
                if now - last_seen_time > self.timeout:
                    self.r.remove_key(self.r.redis_dict, node_jid)
                    print(f"Node {node_jid} removed due to inactivity.")

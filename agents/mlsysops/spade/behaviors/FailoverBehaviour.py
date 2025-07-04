#  Copyright (c) 2025. MLSysOps Consortium
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import json
from spade.behaviour import OneShotBehaviour
from ...logger_util import logger


class FailoverBehavior(OneShotBehaviour):
    def __init__(self, redis_manager, message_queue):
        super().__init__()
        self.r = redis_manager
        self.message_queue = message_queue

    async def run(self):
        logger.info("Starting check for FAILOVER Behaviour")

        # Retrieve all apps and their statuses from Redis
        status_data = self.r.get_dict(self.r.dict_name)
        if not status_data:
            logger.debug("No Apps running on the frameworkF")
            return

        # Filter for deployed apps (case-insensitive)
        deployed_apps = [app_id for app_id, status in status_data.items()
                         if status.lower() == "deployed"]

        # For each deployed app, fetch its data from Redis and send a failover event
        for app_id in deployed_apps:
            app_data = await self.fetch_app_data(app_id)
            await self.message_queue.put({
                "event": "application_submitted",
                "payload": app_data
            })

    async def fetch_app_data(self, app_id: str) -> dict:
        """
        Fetch application data from Redis hash 'app_data_hash' for the given application ID.
        """
        try:
            # Retrieve the serialized dict stored under the app_id key
            raw = self.r.get_dict_value("app_data_hash", app_id)
            if raw is None:
                raise KeyError(f"No data for app_id {app_id} in 'app_data_hash' hash")

            # Parse JSON string into Python dict
            return json.loads(raw)

        except Exception as e:
            logger.error(f"Error fetching data for {app_id} from Redis: {e}")


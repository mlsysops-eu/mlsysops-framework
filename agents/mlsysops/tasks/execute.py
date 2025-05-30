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

from ..tasks.base import BaseTask

from ..logger_util import logger
from ..data.state import MLSState


class ExecuteTask(BaseTask):

    def __init__(self, asset, new_command, state: MLSState = None, plan_uuid=None):
        super().__init__(state)

        self.asset_name = asset
        self.new_command = new_command
        self.state = state
        self.plan_uuid = plan_uuid

    async def run(self):
        logger.debug("Running Execute Task ")
        logger.debug(f"New command: {self.new_command} - plan {self.plan_uuid}")
        logger.debug(f"Asset: {self.asset_name}")

        logger.debug(f"Asset available: {self.state.configuration.mechanisms}")
        logger.debug(f"Asset available: {self.state.assets}")

        if self.asset_name in self.state.configuration.mechanisms and self.asset_name in self.state.assets:
            # Agent is configured to handle this mechanism
            # TODO we can do this check in scheduler?
            mechanism_handler = self.state.assets[self.asset_name]['module']

            print(mechanism_handler)

            try:
                logger.debug(f"Executing command for {self.asset_name} ")
                # Inject plan UUID
                self.new_command["plan_uuid"] = self.plan_uuid
                await mechanism_handler.apply(self.new_command)
                # TODO put some checks?
                self.state.update_task_log(self.plan_uuid, updates={"status": "Pending"})

            except Exception as e:
                logger.error(f"Error executing command: {e}")
                return False

        return True
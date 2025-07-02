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

    def __init__(self, asset, new_command, state: MLSState = None, plan_uid=None):
        super().__init__(state)

        self.asset_name = asset
        self.new_command = new_command
        self.state = state
        self.plan_uid = plan_uid

    async def run(self):

        if self.asset_name in self.state.configuration.mechanisms and self.asset_name in self.state.active_mechanisms:
            # Agent is configured to handle this mechanism
            # TODO we can do this check in scheduler?
            mechanism_handler = self.state.active_mechanisms[self.asset_name]['module']
            logger.debug(f"New command for {self.asset_name} - plan id {self.plan_uid}")

            try:
                # Inject plan UUID
                self.new_command["plan_uid"] = self.plan_uid
                execute_async = await mechanism_handler.apply(self.new_command)
                # TODO introduce fail checks?
                if execute_async:
                    logger.test(
                        f"|1| Plan with planuid:{self.new_command['plan_uid']} executed by applying to mechanism:{self.asset_name} status:Success")
                    self.state.update_plan_status(self.plan_uid, self.asset_name,"Success")
                else:
                    self.state.update_task_log(self.plan_uid, updates={"status": "Pending"})
                    logger.test(
                        f"|1| Plan with planuid:{self.new_command['plan_uid']} executed by applying to mechanism:{self.asset_name} status:Pending")
            except Exception as e:
                logger.error(f"Error executing command: {e}")
                self.state.update_task_log(self.plan_uid, updates={"status": "Failed"})
                return False

        return True
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
    """
    Task to execute a command for a specific mechanism as part of a plan.

    Attributes:
        asset_name (str): Name of the mechanism (e.g., 'cpu', 'gpu').
        new_command (dict): Command details for execution.
        state (MLSState): Shared system state.
        plan_uid (str): Unique identifier of the plan associated with this task.
    """

    def __init__(self, asset: str, new_command: dict, state: MLSState = None, plan_uid: str = None):
        super().__init__(state)
        self.asset_name = asset
        self.new_command = new_command
        self.plan_uid = plan_uid

    async def run(self) -> bool:
        """
        Execute the mechanism's apply method with the provided command.

        Returns:
            bool: True if execution succeeded, False otherwise.
        """
        if not (self.asset_name in self.state.configuration.mechanisms and
                self.asset_name in self.state.active_mechanisms):
            logger.warning(f"Mechanism {self.asset_name} is not active or configured. Skipping execution.")
            return False

        logger.debug(f"Executing command for {self.asset_name} - plan id {self.plan_uid}")

        try:
            # Attach plan UID to command
            self.new_command["plan_uid"] = self.plan_uid

            # Call mechanism apply method
            success = await self.state.active_mechanisms[self.asset_name]['module'].apply(self.new_command)

            if success:
                logger.test(f"|1| Plan {self.plan_uid} executed for mechanism {self.asset_name} - Status: Success")
                self.state.update_plan_status(self.plan_uid, self.asset_name, "Success")
                return True
            else:
                logger.test(f"|1| Plan {self.plan_uid} execution pending for mechanism {self.asset_name}")
                self.state.update_task_log(self.plan_uid, updates={"status": "Pending"})
                return False

        except Exception as e:
            logger.error(f"Error executing command for {self.asset_name}: {e}")
            self.state.update_task_log(self.plan_uid, updates={"status": "Failed"})
            return False

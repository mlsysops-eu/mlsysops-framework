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
import time
import uuid
from datetime import datetime

from ..data.state import MLSState
from mlsysops.controllers.policy import PolicyController, PolicyScopes
from ..policy import Policy
from ..logger_util import logger
from .base import BaseTask
from ..application import MLSApplication
from ..tasks.plan import PlanTask


class AnalyzeTask(BaseTask):
    def __init__(self, id: str, state: MLSState = None, scope: str = "global"):
        super().__init__(state)

        self.id = id
        self.state = state
        self.scope = scope

    async def process_analyze(self, active_policy: Policy):
        start_date = datetime.now()

        current_app_desc = []

        if self.scope == PolicyScopes.APPLICATION.value:
            current_app_desc = [self.state.applications[self.id].app_desc]
        else:
            for app_dec in self.state.applications.values():
                current_app_desc.append(app_dec.app_desc)

        analysis_result = active_policy.analyze(
            current_app_desc,
            self.get_system_description_argument(),
            {},
            self.get_telemetry_argument(),
            {})

        # Add entries
        self.state.add_task_log(
            new_uuid=str(uuid.uuid4()),
            application_id=self.id,
            task_name="Analyze",
            arguments={},
            start_time=start_date,
            end_time=time.time(),
            status="Success",
            result=analysis_result
        )

        logger.debug(f"Analysis Result: {analysis_result}")

        if analysis_result:
            # start a plan task with asyncio create task
            plan_task = PlanTask(self.id, self.state, self.scope)
            asyncio.create_task(plan_task.run())

    async def run(self):
        # TODO put some standard checks. Node load, application component target etc.
        try:
            while True:
                await asyncio.sleep(2)
                logger.debug(f"Analyze Task Running: id: {self.id} scope {self.scope}")
                active_policy = PolicyController().get_policy_instance(self.scope, self.id)
                # active_policy = self.state.policies[0] # for debug

                if active_policy is not None:
                    if self.scope == PolicyScopes.APPLICATION.value:
                        for app_policy_name, app_policy in active_policy.items():
                            logger.debug(f"Active Policy {app_policy_name} for application {self.id} calling analyze")
                            await self.process_analyze(app_policy)
                    else:
                        logger.debug(f"Active Policy calling internal analyze")
                        await self.process_analyze(active_policy)
                else:
                    logger.warn(f"No policy for {self.id}")
                    continue

        except asyncio.CancelledError:
                # Handle task cancellation logic here (clean up if necessary)
                logger.debug("Analyze Task has been cancelled")
                return  # Propagate the cancellation so the task actually stops
        except Exception as e:
            # Handle other exceptions
            logger.error(f"Unexpected exception in AnalyzeTask: {e}")




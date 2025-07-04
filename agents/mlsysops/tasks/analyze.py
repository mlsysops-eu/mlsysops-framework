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
import re
import time
import uuid

from ..controllers import telemetry
from ..data.state import MLSState
from mlsysops.controllers.policy import PolicyController, PolicyScopes
from ..policy import Policy
from ..logger_util import logger
from .base import BaseTask
from ..tasks.plan import PlanTask
from ..controllers.telemetry import parse_interval_string
import traceback


class AnalyzeTask(BaseTask):
    def __init__(self, id: str, state: MLSState = None, scope: str = "global"):
        super().__init__(state)

        logger.warn(f"Created analyzed task for {id}")
        logger.test(f"|1| Starting AnalyzeTask for app:{id} scope:{scope}")
        self.id = id
        self.state = state
        self.scope = scope
        self.analyze_period = 10
        self.analyze_periods = []


    async def process_analyze(self, active_policy: Policy):
        start_date = time.time()

        current_app_desc = []

        if self.scope == PolicyScopes.APPLICATION.value:
            current_app_desc = [self.state.applications[self.id].application_description]
        else:
            for app_dec in self.state.applications.values():
                current_app_desc.append(app_dec.application_description)

        analysis_result = await active_policy.analyze(
            current_app_desc,
            self.get_system_description_argument(),
            self.get_mechanisms(),
            await self.get_telemetry_argument(),
            self.get_ml_connector_object()
        )

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

        # logger.debug(f"Analysis Result: {analysis_result}")
        logger.test(f"|2| Analyze Called for app:{self.id} policy:{active_policy.name} and status:{analysis_result}")
        if analysis_result:
            # start a plan task with asyncio create task
            plan_task = PlanTask(self.id, self.state, self.scope, active_policy.name)
            asyncio.create_task(plan_task.run())

    async def run(self):
        # TODO put some standard checks.
            while True:
                logger.debug(f"Analyze task for {self.id} and scope {self.scope}")
                active_policies = PolicyController().get_policy_instance(self.scope, self.id)

                try:
                    if active_policies is not None:
                        for app_policy_name, app_policy in active_policies:
                            # logger.debug(f"Active Policy {app_policy_name} for application {self.id} calling analyze period {self.analyze_period}")

                            analyze_interval = parse_interval_string(app_policy.get_analyze_period_from_context())
                            self.analyze_periods.append(analyze_interval)
                            if analyze_interval == 0:
                                # run once and exit
                                await self.process_analyze(app_policy)
                                break

                            # Check if we need to run analyze
                            if time.time() - app_policy.last_analyze_run > analyze_interval:
                                await self.process_analyze(app_policy)

                        self.analyze_period = min(self.analyze_periods)
                        self.analyze_periods = []
                    else:
                        logger.warn(f"No policy for {self.id}")

                    await asyncio.sleep(self.analyze_period)
                except asyncio.CancelledError:
                        # Handle task cancellation logic here (clean up if necessary)
                        logger.debug(f"Analyze Task for {self.id} {self.scope} has been cancelled")
                        return  # Propagate the cancellation so the task actually stops
                except Exception as e:
                    # Handle other exceptions
                    logger.error(f"Unexpected exception in AnalyzeTask: {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(self.analyze_period)



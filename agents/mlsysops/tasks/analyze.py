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

from ..data.state import MLSState
from mlsysops.controllers.policy import PolicyController, PolicyScopes
from ..policy import Policy
from ..logger_util import logger
from .base import BaseTask
from ..tasks.plan import PlanTask
import traceback


class AnalyzeTask(BaseTask):
    def __init__(self, id: str, state: MLSState = None, scope: str = "global"):
        super().__init__(state)

        self.id = id
        self.state = state
        self.scope = scope
        self.analyze_period = 10
        self.analyze_periods = []


    async def process_analyze(self, active_policy: Policy):
        start_date = time.time()

        current_app_desc = []

        if self.scope == PolicyScopes.APPLICATION.value:
            current_app_desc = [self.state.applications[self.id].app_desc]
        else:
            for app_dec in self.state.applications.values():
                current_app_desc.append(app_dec.app_desc)

        analysis_result = active_policy.analyze(
            current_app_desc,
            self.get_system_description_argument(),
            {
                "available_assets": self.get_available_assets(),
                "active_assets": self.get_assets()
            },
            self.get_telemetry_argument(),
            self.get_ml_connector_object())

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
            plan_task = PlanTask(self.id, self.state, self.scope, active_policy.name)
            asyncio.create_task(plan_task.run())

    async def run(self):
        # TODO put some standard checks.
            while True:
                logger.debug(f"Analyze Task Running: id: {self.id} scope {self.scope}")
                active_policies = PolicyController().get_policy_instance(self.scope, self.id)
                try:

                    if active_policies is not None:
                        for app_policy_name, app_policy in active_policies:
                            logger.debug(f"Active Policy {app_policy_name} for application {self.id} calling analyze")

                            analyze_interval = parse_analyze_interval(app_policy.get_analyze_period_from_context())
                            self.analyze_periods.append(analyze_interval)
                            if analyze_interval == 0:
                                # run once and exit
                                await self.process_analyze(app_policy)
                                break
                            # Check if we need to run analyze
                            if time.time() - app_policy.last_analyze_run > analyze_interval:
                                logger.debug("Calling process")
                                await self.process_analyze(app_policy)


                        self.analyze_period = min(self.analyze_periods)
                        logger.debug(f"New analyze period: {self.analyze_period} with {self.analyze_periods}")
                        self.analyze_periods = []
                        await asyncio.sleep(self.analyze_period)
                    else:
                        logger.warn(f"No policy for {self.id}")
                        await asyncio.sleep(30)
                        continue

                except asyncio.CancelledError:
                        # Handle task cancellation logic here (clean up if necessary)
                        logger.debug("Analyze Task has been cancelled")
                        return  # Propagate the cancellation so the task actually stops
                except Exception as e:
                    # Handle other exceptions
                    logger.error(f"Unexpected exception in AnalyzeTask: {e}")
                    logger.error(traceback.format_exc())

                    await asyncio.sleep(10)


def parse_analyze_interval(interval: str) -> int:
    """
    Parses an analyze interval string in the format 'Xs|Xm|Xh|Xd' and converts it to seconds.

    Args:
        interval (str): The analyze interval as a string (e.g., "5m", "2h", "1d").

    Returns:
        int: The interval in seconds.

    Raises:
        ValueError: If the format of the interval string is invalid.
    """
    # Match the string using a regex: an integer followed by one of s/m/h/d
    match = re.fullmatch(r"(\d+)([smhd])", interval)
    if not match:
        raise ValueError(f"Invalid analyze interval format: '{interval}'")

    # Extract the numeric value and the time unit
    value, unit = int(match.group(1)), match.group(2)

    # Convert to seconds based on the unit
    if unit == "s":  # Seconds
        return value
    elif unit == "m":  # Minutes
        return value * 60
    elif unit == "h":  # Hours
        return value * 60 * 60
    elif unit == "d":  # Days
        return value * 24 * 60 * 60
    else:
        raise ValueError(f"Unsupported time unit '{unit}' in interval: '{interval}'")




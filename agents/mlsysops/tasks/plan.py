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

import uuid
from dataclasses import dataclass, field

from ..policy import Policy
from ..data.plan import Plan
from ..application import MLSApplication
from ..tasks.base import BaseTask
import time
from ..logger_util import logger
from ..data.state import MLSState
from ..controllers.policy import PolicyController, PolicyScopes
import uuid

class PlanTask(BaseTask):

    def __init__(self, id: str, state: MLSState = None, scope: str = "global", policy_name: str = None):
        super().__init__(state)

        self.id = id
        self.state = state
        self.scope = scope
        self.policyName = policy_name

    async def process_plan(self, current_app_desc, active_policy: Policy):
        start_date = time.time()
        plan_result = await active_policy.plan(
            current_app_desc,
            self.get_system_description_argument(),
            self.get_mechanisms(),
            await self.get_telemetry_argument(),
            self.get_ml_connector_object()
        )

        uuid4 = str(uuid.uuid4())

        new_plan = Plan(uuid=uuid4, asset_new_plan=plan_result, application_id=self.id, core=active_policy.core)
        assets = {}

        for asset, _ in plan_result.items():
            assets[asset] = "Pending"

        # Add entries
        self.state.add_task_log(
            new_uuid=new_plan.uuid,
            application_id=self.id,
            task_name="Plan",
            arguments={},
            start_time=start_date,
            end_time=time.time(),
            status="Queued",
            plan=plan_result,
            mechanisms=assets
        )

        logger.test(f"|1| Plan call for app:{self.id} from policy:{active_policy.name} of assets {assets} and planuid:{new_plan.uuid}")

        # put the new plan to the queue - scheduler
        await self.state.plans.put(new_plan)

    async def run(self):
        """
        Asynchronously runs the process of retrieving and processing active policy plans based
        on the provided scope and policy name. Determines and processes application-specific
        or global policies accordingly.

        Returns:
            bool: Always returns True upon successful execution.

        Raises:
            Exception: An unhandled exception will propagate if encountered within the method.

        """
        active_policy = PolicyController().get_policy_instance(self.scope,self.id,self.policyName)

        if active_policy is not None:

            # Call policy re_plan for this application
            logger.debug(f"Calling Policy plan {self.id} ")

            current_app_desc = []

            if self.scope == PolicyScopes.APPLICATION.value:
                current_app_desc = [self.state.applications[self.id].application_description]
                for app_policy_name, app_policy in active_policy.items():
                    await self.process_plan(current_app_desc,app_policy)
            else:
                for app_dec in self.state.applications.values():
                    current_app_desc.append(app_dec.application_description)
                await self.process_plan(current_app_desc, active_policy)


        return True


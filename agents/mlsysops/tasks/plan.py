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

from ..data.plan import Plan
from ..application import MLSApplication
from ..tasks.base import BaseTask
import time
from ..logger_util import logger
from ..data.state import MLSState
from ..controllers.policy import PolicyController
import uuid

class PlanTask(BaseTask):

    def __init__(self, application: MLSApplication = None, state: MLSState = None):
        super().__init__()

        self.application = application
        self.state = state

    async def run(self):
        logger.debug("Running Plan Task")
        active_policy = PolicyController().get_policy_for_application(self.application.application_id)
        if active_policy is not None:
            start_date = time.time()

            # Call policy re_plan for this application
            plan_result = active_policy.plan({},self.application.component_spec, {}, {}, {}, {})


            logger.debug("Plan Result: ", plan_result)
            uuid4 = str(uuid.uuid4())

            new_plan = Plan(uuid=uuid4,asset_new_plan=plan_result)

            # Add entries
            self.state.add_task_log(
                new_uuid=new_plan.uuid,
                application_id=self.application.application_id,
                task_name="Plan",
                arguments={},
                start_time=start_date,
                end_time=time.time(),
                status="Queued",
                result=new_plan
            )

            # put the new plan to the queue - scheduler
            await self.state.plans.put(new_plan)

        return True


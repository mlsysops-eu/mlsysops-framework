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
from ..controllers.policy import PolicyController
from ..logger_util import logger
from .base import BaseTask
from ..application import MLSApplication
from ..tasks.plan import PlanTask


class AnalyzeTask(BaseTask):
    def __init__(self, application: MLSApplication = None, state: MLSState = None):
        super().__init__()

        self.application = application
        self.state = state


    async def run(self):
        # TODO put some standard checks. Node load, application component target etc.

        print("Analyze Task Running")
        while True:
            await asyncio.sleep(2)
            logger.debug(f"Analyze Task Running")
            # test - get policy
            active_policy = PolicyController().get_policy_for_application(self.application.application_id)
            if active_policy is not None:
                start_date = datetime.now()

                analysis_result = active_policy.analyze(self.application.component_spec,{},{}, {}, {})

                # Add entries
                self.state.add_task_log(
                    new_uuid=str(uuid.uuid4()),
                    application_id=self.application.application_id,
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
                  plan_task = PlanTask(self.application,self.state)
                  asyncio.create_task(plan_task.run())




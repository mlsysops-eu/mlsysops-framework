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
import json
import time

from .tasks import ExecuteTask
from .logger_util import logger
from .data.plan import Plan
from .data.task_log import Status

class PlanScheduler:
    def __init__(self, state):
        self.state = state
        self.period = 5
        self.pending_plans = []

    async def update_pending_plans(self):
        for pending_plan in self.pending_plans:
            task_log = self.state.get_task_log(pending_plan.uuid)
            if task_log.status != Status.PENDING:
                self.pending_plans.remove(pending_plan) # remove it

    async def run(self):
        logger.debug("PlanScheduler started")
        while True:
            await asyncio.sleep(self.period)  # Wait for 1 second
            current_plan_list: list[Plan] = []

            logger.debug("--------------Scheduler Loop------")

            # check for previous plans
            await self.update_pending_plans()

            # Empty the queue
            while not self.state.plans.empty():
                # Get plans from queue
                item = await self.state.plans.get()
                current_plan_list.append(item)
                self.state.plans.task_done()  # Mark task as done

            # initialize auxiliary dicts
            assets_touched = {}
            logger.debug(f"Current plan list: {len(current_plan_list)}")
            if len(current_plan_list) > 0:

                for plan in current_plan_list:
                    logger.debug(f"Processing {str(plan.uuid)} plan")

                    # Use FIFO logic - execute the first plan, and save the mechanisms touched.
                    # TODO declare mechanisms as singletons or multi-instanced.
                    # Singletons (e.g. CPU Freq): Can be configured once per Planning/Execution cycle, as they have
                    # global effect
                    # Multi-instance (e.g. component placement): Configure different parts of the system, that do not
                    # affect anything else

                    # Iterating over key-value pairs
                    for asset, command in plan.asset_new_plan.items():
                        print(f"asset: {asset}")
                        print(f"command: {command}")
                        should_discard = False

                        # if was executed a plan earlier, then discard it.
                        if asset in assets_touched:
                            should_discard = True

                        task_log = self.state.get_task_log(plan.uuid)

                        # Check if there is a pending task log from previous runs
                        if task_log:
                            if (task_log['status'] == Status.PENDING.value
                                    and task_log['asset'][asset] == Status.PENDING.value):
                                should_discard = True

                        # check if the application has been removed for this application scoped plan
                        if plan.application_id not in self.state.applications:
                            should_discard = True

                        # TODO: check for fluidity debug
                        # Check if it is core, should override the discard mechanism
                        logger.debug(f"_-------------------> {plan}")
                        if not plan.core and should_discard:
                            logger.debug(f"Discarding plan {str(plan.uuid)}")
                            self.state.update_task_log(plan.uuid,updates={"status": "Discarded"})
                            continue


                        self.state.update_task_log(plan.uuid,updates={"status": "Scheduled"})

                        # mark asset touched only for non-core
                        if not plan.core:
                            assets_touched[asset] = {
                                "timestamp": time.time(),
                                "plan_uuid": plan.uuid,
                                "plan": command
                            }

                        # start execution task
                        plan_task = ExecuteTask(asset,command, self.state, plan.uuid)
                        asyncio.create_task(plan_task.run())

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

from .tasks import ExecuteTask
from .logger_util import logger
from .data.plan import Plan

class PlanScheduler:
    def __init__(self, state):
        self.state = state
        self.period = 5

    async def run(self):
        logger.debug("PlanScheduler started")
        while True:
            await asyncio.sleep(self.period)  # Wait for 1 second
            current_plan_list: list[Plan] = []

            logger.debug("--------------Scheduler Loop------")

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
                    # TODO declare mechanisms as singletons or multi-instnaced.
                    # Singletons (e.g. CPU Freq): Can be configured once per Planning/Execution cycle, as they have
                    # global effect
                    # Multi-instance (e.g. component placement): Configure different parts of the system, that do not
                    # affect anything else

                    # Iterating over key-value pairs
                    for asset, command in plan.asset_new_plan.items():
                        print(f"asset: {asset}")
                        print(f"command: {command}")
                        if asset in assets_touched:
                            # if was executed a plan earlier, then discard it.
                            self.state.update_task_log(plan.uuid,updates={"status": "Discarded"})
                            continue

                        self.state.update_task_log(plan.uuid,updates={"status": "Scheduled"})

                        # mark asset touched
                        assets_touched[asset] = {
                            "timestamp": time.time(),
                            "plan": command
                        }

                        # start execution task
                        plan_task = ExecuteTask(asset,command, self.state, plan.uuid)
                        asyncio.create_task(plan_task.run())

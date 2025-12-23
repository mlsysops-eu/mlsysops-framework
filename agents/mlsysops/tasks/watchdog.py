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

import asyncio
import time

from mlsysops.data.state import MLSState
from mlsysops.data.task_log import Status
from mlsysops.logger_util import logger


class WatchdogTask:
    """
    Periodically scans MLSState.task_log and marks Pending tasks as Failed
    when they exceed the configured TTL.

    TTL source order:
      1. Per-task override in 'arguments' (if provided by policy) under key 'ttl'.
      2. Global state.task_ttl (can be set from environment or policy context).
    """

    def __init__(self, state: MLSState):
        self.state = state
        self.interval_seconds = float(self.state.configuration.watchdog_interval)

    async def run(self):
        while True:
            try:
                await asyncio.sleep(self.interval_seconds)
                self._check_for_expired_tasks()
            except asyncio.CancelledError:
                logger.debug("WatchdogTask cancelled, stopping.")
                break
            except Exception as exc:
                logger.warning(f"WatchdogTask encountered an error: {exc}")

    def _check_for_expired_tasks(self):
        df = self.state.task_log
        if df.empty:
            return

        now = time.time()

        # Only Pending tasks
        pending_mask = df["status"] == Status.PENDING.value
        if not pending_mask.any():
            return

        pending_df = df[pending_mask]

        logger.debug(f"Found {len(pending_df)} pending tasks to check for expiration.")

        for _, row in pending_df.iterrows():
            try:
                start_time = float(row["start_time"])
            except Exception:
                # If start_time is malformed, skip this row
                continue

            # Per-task TTL from arguments if provided by policy
            per_task_ttl = None
            arguments = row.get("arguments")
            if isinstance(arguments, dict):
                per_task_ttl = arguments.get("ttl")

            try:
                ttl = float(per_task_ttl) if per_task_ttl is not None else float(self.state.configuration.task_ttl)
            except Exception:
                ttl = float(self.state.configuration.task_ttl)

            if now - start_time > ttl:
                plan_uid = row["uuid"]
                logger.debug(
                    f"Watchdog expiring task {plan_uid}: "
                    f"start_time={start_time}, now={now}, ttl={ttl}"
                )
                # Mark as Failed and update end_time
                self.state.update_task_log(
                    plan_uid,
                    updates={
                        "status": Status.FAILED.value,
                        "end_time": now,
                    },
                )

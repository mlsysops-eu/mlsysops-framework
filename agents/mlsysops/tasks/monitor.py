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
from datetime import datetime
from typing import Any, Optional, Dict, List
from mlstelemetry import MLSTelemetry
from mlsysops.data.monitor import MonitorData

from mlsysops.logger_util import logger
from mlsysops.controllers.telemetry import parse_interval_string

class MonitorTask:
    """
    Represents a task responsible for monitoring metrics, collecting telemetry data,
    and managing metrics in a thread-safe manner.

    The MonitorTask class is designed to periodically retrieve telemetry data for a list of
    monitored metrics. It provides methods to add, remove, list, and clear metrics while ensuring
    thread-safe access to the underlying list. The `run` method serves as the main loop for
    fetching telemetry data.

    Attributes:
        queue: The queue to process messages if required (purpose not described in this code).
        __data: Object storing telemetry data collected from metrics.
        period: An optional period (in seconds) between execution cycles in the `run` method.
        metrics_list: A thread-safe list holding the names of monitored metrics.
        mlsTelemetryClient: An MLSTelemetry instance used for fetching metrics telemetry data.
    """
    def __init__(self, state, queue, period = "5s"):
        self.__lock = asyncio.Lock()  # Lock to ensure thread-safe access
        self.state = state
        self.queue = queue
        self.__data: MonitorData = state.monitor_data
        self.period = parse_interval_string(period)

        # A list of metrics that this monitor
        self.metrics_list = []

        self.mlsTelemetryClient = MLSTelemetry("monitor_task","-")

    async def set_monitor_interval(self, new_period):
        """
        Changes the monitoring interval.
        This function is asynchronous and modifies the interval in a non-blocking
        manner.

        Args:
            new_period (int): The new period to set for the monitoring interval.
        """
        self.period = new_period

    async def add_metric(self, metric: Any) -> None:
        """
        Add a metric to the metrics list in a thread-safe manner.

        :param metric: The metric to add.
        """
        async with self.__lock:
            if metric not in self.metrics_list:
                self.metrics_list.append(metric)
                logger.debug(f"Metric added: {metric}")
            else:
                logger.debug(f"Metric already exists: {metric}")

    async def remove_metric(self, metric: Any) -> bool:
        """
        Remove a metric from the metrics list in a thread-safe manner.

        :param metric: The metric to remove.
        :return: True if removed, False if not found.
        """
        async with self.__lock:
            if metric in self.metrics_list:
                self.metrics_list.remove(metric)
                logger.debug(f"Metric removed: {metric}")
                return True
            else:
                logger.debug(f"Metric not found: {metric}")
                return False

    async def list_metrics(self) -> List[Any]:
        """
        Retrieve the current metrics list in a thread-safe manner.

        :return: A thread-safe copy of the metrics list.
        """
        async with self.__lock:
            return list(self.metrics_list)

    async def clear_metrics(self) -> None:
        """
        Clear all metrics from the list in a thread-safe manner.
        """
        async with self.__lock:
            self.metrics_list.clear()
            logger.debug("All metrics cleared.")

    async def run(self):
        logger.debug("Monitor task running")
        try:
            while True:
                await asyncio.sleep(self.period)

                async with self.__lock:  # Locking ensures safe iteration if list is modified concurrently
                    current_time = time.time()
                    # Fetch telemetry data
                    for metric_name in self.metrics_list:
                        # logger.debug(f"Fetching telemetry for metric: {metric_name}")
                        try:
                            # Call get_metric_value_with_label for the metric
                            metric_status = self.mlsTelemetryClient.get_metric_value_with_label(
                                metric_name=metric_name
                            )
                            # Add metric value to __data in the format {metric_name: value}
                            # Metric name will be the column, and its value will be the specific recorded data
                            entry = {
                                metric_name: metric_status[0]['value'],
                                "timestamp": current_time,
                                "human_timestamp": datetime.fromtimestamp(int(current_time)).strftime('%Y-%m-%d %H:%M:%S')
                            } # TODO handle multiple values and timestamp
                            logger.debug(f"Telemetry for metric '{metric_name}': {entry}")
                            await self.__data.add_entry(entry)

                        except Exception as e:
                            #logger.error(f"Error fetching telemetry for metric '{metric_name}': {str(e)}")
                            pass
                    # Fetch mechanisms state
                    for mechanism_key, mechanism_object in self.state.active_mechanisms.items():
                        mechanism_object['state'] = mechanism_object['module'].get_state()

        except asyncio.CancelledError:
            logger.debug(f"Monitor task cancelled.")
        except Exception as e:
           logger.error(f"Unexpected error during telemetry collection: {str(e)}")
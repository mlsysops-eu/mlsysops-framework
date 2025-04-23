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
from typing import List, Dict, Any

from ..application import MLSApplication
from ..data.state import MLSState
from ..tasks.monitor import MonitorTask

from ..tasks.analyze import AnalyzeTask


class ApplicationController:
    """
    The ApplicationController handles application lifecycle events,
    communicates with the monitor task, and manages application data.
    """

    def __init__(self, monitor_task: MonitorTask, state: MLSState = None):
        """
        Initialize the ApplicationController.

        :param monitor_task: Instance of the MonitorTask class.
        """
        self.monitor_task = monitor_task
        self.state = state
        self.application_tasks_running = {}

    async def on_application_received(self, application_data: Dict):
        """
        Processes received application data, creates a new application instance, adds it to the state,
        and starts an analysis task for the application.

        Args:
            application_data: A dictionary containing the application's component name and specifications.

        Raises:
            KeyError: If the required keys are missing in the application_data.

        """
        print(f"Received application: {application_data}")

        # Create and store a new MLSApplication instance
        new_application = MLSApplication(
            application_id=application_data["component_name"],
            component_spec=application_data["comp_specs"]
        )
        self.state.add_application(new_application.application_id, new_application)

        # # Update the monitoring list for the application's metrics
        # for metric_name in application_data["component_spec"]["metrics"]:
        #     await self.monitor_task.add_metric(metric_name)

        # Start an analyze task for this application
        analyze_task = AnalyzeTask(new_application,self.state)
        asyncio.create_task(analyze_task.run())

        self.application_tasks_running[new_application.application_id] = analyze_task

    async def on_application_terminated(self, application_id: str):
        """
        Cancels and removes a running application task upon termination request.

        This method is triggered when an application with a specified application_id
        is terminated. It cancels the associated running task if it exists in the
        application_tasks_running dictionary and removes it from the dictionary.

        Parameters:
            application_id (str): The unique identifier of the application
                                  being terminated.
        """
        # terminate task
        if application_id in self.application_tasks_running:
            self.application_tasks_running[application_id].cancel()
            del self.application_tasks_running[application_id]

    async def run(self):
        """
        Continuously checks the state for new applications and handles them.
        """
        while True:
            for app_id, app_object in MLSState.applications.items():
                print(f'Application {app_id}')

            # Check periodically (adjust the sleep interval as needed)
            await asyncio.sleep(10)
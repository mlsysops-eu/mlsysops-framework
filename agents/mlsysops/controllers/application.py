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
from typing import Dict
from ..logger_util import logger
from ..application import MLSApplication
from ..data.state import MLSState
from ..tasks.analyze import AnalyzeTask


class ApplicationController:
    """
    The ApplicationController handles application lifecycle events,
    communicates with the monitor task, and manages application data.
    """

    def __init__(self, agent):
        """
        Initialize the ApplicationController.

        :param monitor_task: Instance of the MonitorTask class.
        """
        self.agent = agent
        self.application_tasks_running = {}

    def  __del__(self):
        """
        Cancels and clears all running application tasks upon deletion.

        Returns:
            None
        """
        for app_id, task in self.application_tasks_running.items():
            task.cancel()
        self.application_tasks_running.clear()

    async def on_application_received(self, application_data: Dict):
        """
        Processes received application data, creates a new application instance, adds it to the state,
        and starts an analysis task for the application.

        Args:
            application_data: A dictionary containing the application's component name and specifications.

        Raises:
            KeyError: If the required keys are missing in the application_data.

        """
        # Create and store a new MLSApplication instance
        new_application = MLSApplication(
            application_id=application_data["name"],
            application_description=application_data
        )
        
        self.agent.state.add_application(new_application.application_id, new_application)

        # Update the monitoring list for the application's metrics
        for component in application_data.get("spec", {}).get("components", []):
            qos_metrics = component.get("qos_metrics", [])
            for qos_metric in qos_metrics:
                metric_name = qos_metric.get("application_metric_id")
                if metric_name:  # Ensure the metric name exists
                    await self.agent.monitor_task.add_metric(metric_name)

        # Start an analyze task for this application
        analyze_object = AnalyzeTask(new_application.application_id,self.agent.state, "application")
        analyze_task = asyncio.create_task(analyze_object.run())

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
        if application_id in self.application_tasks_running:
            logger.debug(f"Terminating application {application_id} with list {self.application_tasks_running}")
            # NOTE: Does this only cancel analyze tasks?
            self.application_tasks_running[application_id].cancel()
            del self.application_tasks_running[application_id]
            self.agent.state.remove_application(application_id)

    async def on_application_updated(self, data):
        """
        Handles updates for a specific application by checking if it is currently running
        and updates its state accordingly.

        Args:
            data (dict): A dictionary containing information about the updated application, including its name.

        Raises:
            None
        """
        if data['name'] in self.application_tasks_running:
            self.agent.state.update_application(data['name'],data)
        else:
            logger.error(f'No application {data["name"]} found.')

    async def run(self):
        """
        Continuously checks the state for new applications and handles them.
        """
        while True:
            for app_id, app_object in MLSState.applications.items():
                print(f'Application {app_id}')

            # Check periodically (adjust the sleep interval as needed)
            await asyncio.sleep(10)
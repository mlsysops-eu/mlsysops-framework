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
import os
import pickle
import socket
import tempfile
import time
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Dict, List, Optional, Any

import pandas as pd

from ..application import MLSApplication
from ..data.configuration import AgentConfig
from ..data.monitor import MonitorData
from ..data.plan import Plan
from ..data.task_log import TaskLogEntry, Status
from ..logger_util import logger
from ..policy import Policy


@dataclass
class MLSState:
    """
    Represents a KnowledgeBase that manages application state, monitoring data, and task logs.

    This class provides functionality for saving and loading the state, which includes monitor data,
    applications, task logs, and policy configurations. It also supports periodic state saving tasks
    to ensure the data persistence over time.

    Attributes:
        monitor_data (Dict[str, MonitorData]): Map of application identifiers to their corresponding
            monitoring data.
        applications (Dict[str, MLSApplication]): Map of keys to MLSApplication instances.
        task_log (pd.DataFrame): DataFrame holding the task log entries.
        policy (Policy): The policy object determining operational rules and configurations.
        _save_period (int): The time interval, in seconds, between automatic save operations.
        _lock (asyncio.Lock): Ensures thread-safe operations during save/load processes.
        _save_task (asyncio.Task): Asyncio task for periodic saving.
        _last_save_file (str): Tracks the last file used for saving state, enabling recovery.
    """
    monitor_data: MonitorData = MonitorData()
    applications: Dict[str, MLSApplication] = field(default_factory=dict)
    task_log: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            [],
            columns=[f.name for f in fields(TaskLogEntry)]
        )
    )
    plans: asyncio.Queue[Plan] = field(default_factory=asyncio.Queue)
    active_mechanisms: Dict = field(default_factory=dict)
    policies: Dict[str, Policy] = field(default_factory=dict)
    hostname: str = field(default_factory=lambda: os.getenv("NODE_NAME", socket.gethostname()))
    configuration: AgentConfig = None
    agent: object = None
    _save_period: int = 300  # Period (in seconds) for saving the state
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)  # Lock for thread safety
    _save_task: asyncio.Task = field(default=None, init=False)  # Task for periodic saving
    _last_save_file: str = field(default=None, init=False)  # Tracks the last save file for reloading
    _log_dump_task: asyncio.Task = field(default=None, init=False)  # Task for periodic log dump

    def add_application(self, app_id: str, application: MLSApplication):
        """
        Add a new application to the applications dictionary.
        :param app_id: Key to identify the application.
        :param application: MLSApplication instance to add.
        :raises ValueError: If app_id already exists in the dictionary.
        """
        if app_id in self.applications:
            logger.error(f"Application with ID '{app_id}' already exists.")
            return

        self.applications[app_id] = application
        logger.debug(f"Application '{app_id}' added successfully.")

    def remove_application(self, app_id: str):
        """
        Remove an application from the applications dictionary.
        :param app_id: The ID of the application to remove.
        :raises KeyError: If app_id does not exist in the dictionary.
        """
        if app_id not in self.applications:
            raise KeyError(f"Application with ID '{app_id}' does not exist.")
        del self.applications[app_id]
        logger.debug(f"Application '{app_id}' removed successfully.")

    def update_application(self, app_id:str, app_desc: any):

        if app_id not in self.applications:
            raise KeyError(f"Application with ID '{app_id}' does not exist.")
        self.applications[app_id].application_description = app_desc
        logger.info(f"Application '{app_id}' updated successfully.")

    def add_policy(self, policy_name: str, policy: Policy):
        """
        Add a new Policy object to the policies dictionary.
        :param policy_name: The name or identifier of the policy.
        :param policy: The Policy object to be added.
        :raises ValueError: If a policy with the same name already exists.
        """
        if policy_name in self.policies:
            raise ValueError(f"Policy '{policy_name}' already exists.")
        self.policies[policy_name] = policy
        logger.debug(f"Policy '{policy_name}' added successfully.")

    def remove_policy(self, policy_name: str):
        """
        Remove a specified Policy object from the policies dictionary.
        :param policy_name: The name or identifier of the policy to be removed.
        :raises KeyError: If the policy does not exist in the dictionary.
        """
        if policy_name not in self.policies:
            raise KeyError(f"Policy '{policy_name}' does not exist.")
        del self.policies[policy_name]
        logger.debug(f"Policy '{policy_name}' removed successfully.")

    def policy_exists(self, policy_name: str) -> bool:
        """
        Check if a policy exists in the policies dictionary.
        :param policy_name: The name or identifier of the policy to check.
        :return: True if the policy exists, False otherwise.
        """
        return policy_name in self.policies

    def get_policy(self, policy_name: str) -> Optional[Policy]:
        """
        Retrieve a policy by its name from the policies dictionary.
        :param policy_name: The name or identifier of the policy to retrieve.
        :return: The Policy object if it exists, None otherwise.
        """
        return self.policies.get(policy_name, None)

    async def save_state(self):
        """
        Save the current state of the DataHolder class to a temporary file using pickle.
        This ensures the state can be restored later.
        """
        async with self._lock:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl")
            with open(temp_file.name, "wb") as f:
                pickle.dump({
                    "monitor_data": self.monitor_data,
                    "applications": self.applications,
                    "policy": self.policies
                }, f)
            self.task_log.to_pickle("temp_task_log.pkl", protocol=4)
            self._last_save_file = temp_file.name  # Track the last save location
            logger.info(f"State saved to {temp_file.name}")

    async def load_state(self, file_path: str = None):
        """
        Load the state of the DataHolder class from a pickle file.

        :param file_path: The path to the pickle file to load. If None, attempts to use the last saved file.
        """
        async with self._lock:
            file_to_load = file_path or self._last_save_file

            if not file_to_load or not os.path.exists(file_to_load):
                raise FileNotFoundError(f"File {file_to_load} does not exist.")

            with open(file_to_load, "rb") as f:
                state = pickle.load(f)
                self.monitor_data = state.get("monitor_data", {})
                self.applications = state.get("applications", {})
                self.policies = state.get("policy", None)
                self.task_log = pd.read_pickle("temp_task_log.pkl")
            logger.info(f"State loaded from {file_to_load}")

    async def _periodic_save(self):
        """
        Periodically save the state of the class every `_save_period` seconds.
        """
        while True:
            await asyncio.sleep(self._save_period)
            await self.save_state()

    def start_periodic_save(self):
        """
        Start the asyncio task to save state periodically.
        """
        if not self._save_task or self._save_task.done():
            self._save_task = asyncio.create_task(self._periodic_save())

    def stop_periodic_save(self):
        """
        Stop the periodic saving task if it is running.
        """
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()

    async def _period_log_dump(self):
        while True:
            await asyncio.sleep(1)
            self.task_log.to_csv(f"task_log_{self.configuration.node}.csv",index=False)

    def start_period_log_dump(self):
        if not self._log_dump_task or self._log_dump_task.done():
            self._log_dump_task = asyncio.create_task(self._period_log_dump())


    def add_task_log(self, new_uuid: str, application_id: str, task_name: str, arguments: Dict[str, Any], start_time: float,
                     end_time: float, status: Optional[str] = None, plan: Optional[Any] = None, mechanisms: Optional[Dict] = None, result: Optional[Any] = None):
        """
        Adds a new task log entry to the task_log list.
        """
        entry = TaskLogEntry(
            uuid=new_uuid,
            timestamp=time.time(),
            application_id=application_id,
            task_name=task_name,
            arguments=arguments,
            start_time=start_time,
            end_time=end_time,
            status=status,
            plan=json.dumps(plan),
            result=json.dumps(result),
            mechanism=json.dumps(mechanisms) if mechanisms else None
        )

        new_row = pd.DataFrame([entry.to_dict()])
        self.task_log = pd.concat([self.task_log, new_row], ignore_index=True)

    def remove_task_log(self, timestamp: datetime):
        """
        Removes task log entry(ies) from the task_log DataFrame by its timestamp.
        """
        mask = self.task_log['timestamp'] != timestamp
        original_size = len(self.task_log)
        self.task_log = self.task_log[mask].reset_index(drop=True)

        if len(self.task_log) < original_size:
            logger.debug(f"Task log entry with timestamp {timestamp} removed.")
        else:
            logger.debug(f"No task log entry found with timestamp {timestamp}.")

    def update_task_log(self, uuid: str, updates: Dict[str, Any]):
        """
        Updates the task log with the provided changes for a specific task identified
        by its UUID.

        The method locates the row in the task log that matches the given UUID and
        applies the updates to the specified columns. If no matching UUID is found,
        a warning is logged, and the method returns False.

        Args:
            uuid (str): The unique identifier representing the task to be updated.
            updates (Dict[str, Any]): A dictionary containing column names as keys and
                respective values to be updated.

        Returns:
            bool: True if the task log was successfully updated, False otherwise.
        """
        # Locate the row where the uuid matches
        row_index = self.task_log[self.task_log['uuid'] == uuid].index

        if not row_index.empty:
            # Update the specific columns with new values
            for column, value in updates.items():
                self.task_log.loc[row_index, column] = value
            return True
        else:
            logger.warning(f"No task log entry found with uuid={uuid}")
            return False

    def get_task_log(self, uuid: str):
        result = self.task_log[self.task_log['uuid'] == uuid].reset_index(drop=True).to_dict(orient='records')
        row =  result[0] if result else None
        if row:
            row['mechanism'] = json.loads(row['mechanism'])
        return row

    def update_plan_status(self,plan_uid:str, mechanism: str, status:str):
        """
        Updates the status of a specific mechanism in the task log associated with the given
        plan UID and checks if all mechanisms are completed. If all mechanisms are completed,
        it marks the task as completed in the log.

        Args:
            plan_uid (str): The unique identifier of the plan.
            mechanism (str): The name of the mechanism to update.
            status (str): The new status of the mechanism.

        Returns:
            bool: True if the task log was updated successfully, False otherwise.
        """
        # Get the current task log
        task_log = self.get_task_log(plan_uid)

        if not task_log:
            return False

        # Update the specific mechanism's status
        if mechanism in task_log['mechanism']:
            task_log["mechanism"][mechanism] = status  # Set the status for the specific asset

            # Check if all active_mechanisms are True
            all_assets_status = all(value != "Pending" for value in task_log["mechanism"].values())
            updates = {"mechanism": json.dumps(task_log["mechanism"])}

            if all_assets_status:
                updates['status'] = Status.COMPLETED.value

            # Send updates to the task log
            return self.update_task_log(plan_uid, updates=updates)
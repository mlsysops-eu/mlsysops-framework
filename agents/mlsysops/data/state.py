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
import json
import socket
import time
import types
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime
from typing import Dict, List, BinaryIO, Optional, Any
import asyncio
import pickle
import tempfile
import os
import pandas as pd
import uuid

from ..logger_util import logger
from ..application import MLSApplication
from ..data.configuration import AgentConfig
from ..data.monitor import MonitorData
from ..data.task_log import TaskLogEntry
from ..policy import Policy
from ..data.plan import Plan

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
    applications: Dict[str, MLSApplication] = field(default_factory=dict)  # Map of key to MLSApplication
    task_log: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            columns=[f.name for f in fields(TaskLogEntry)]
        )
    )
    plans: asyncio.Queue[Plan] = field(default_factory=asyncio.Queue)
    assets: Dict = field(default_factory=dict)
    policies: List[Policy] = field(default_factory=list)
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
            raise ValueError(f"Application with ID '{app_id}' already exists.")

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
        self.applications[app_id].app_desc = app_desc
        logger.info(f"Application '{app_id}' updated successfully.")

    def add_policy(self, policy: Policy):
        """
        Add a new Policy object to the policy list.
        :param policy: The Policy object to be added.
        """
        self.policies.append(policy)

    def remove_policy(self, policy: Policy):
        """
        Remove a specified Policy object from the policy list.
        :param policy: The Policy object to be removed.
        :raises ValueError: If the policy does not exist in the list.
        """
        if policy not in self.policies:
            raise ValueError("The specified policy does not exist.")
        self.policies.remove(policy)


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
            print(f"State saved to {temp_file.name}")

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
            print(f"State loaded from {file_to_load}")

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
            await asyncio.sleep(10)
            logger.debug("Dumping task log...")
            self.task_log.to_csv("task_log.csv",index=False)

    def start_period_log_dump(self):
        if not self._log_dump_task or self._log_dump_task.done():
            self._log_dump_task = asyncio.create_task(self._period_log_dump())


    def add_task_log(self, new_uuid: str, application_id: str, task_name: str, arguments: Dict[str, Any], start_time: float,
                     end_time: float, status: Optional[str] = None, result: Optional[Any] = None, assets: Optional[Dict] = None):
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
            result=json.dumps(result),
            asset=json.dumps(assets) if assets else None
        )

        new_row = pd.DataFrame([entry.to_dict()])
        self.task_log = pd.concat([self.task_log, new_row], ignore_index=True)

        logger.debug(f"Added task log entry: {entry}")

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
        Updates an existing task log entry in the task_log DataFrame using the specified uuid.

        :param uuid: The unique identifier of the task log entry to update.
        :param updates: A dictionary containing column names as keys and the new values to be updated.
        """
        # Locate the row where the uuid matches
        row_index = self.task_log[self.task_log['uuid'] == uuid].index

        if not row_index.empty:
            # Update the specific columns with new values
            for column, value in updates.items():
                self.task_log.loc[row_index, column] = value

            logger.debug(f"Updated task log entry for uuid={uuid} with updates: {updates}")
        else:
            logger.warning(f"No task log entry found with uuid={uuid}")

    def get_task_log(self, uuid: str):
        result = self.task_log[self.task_log['uuid'] == uuid].reset_index(drop=True).to_dict(orient='records')
        row =  result[0] if result else None
        row["asset"] = json.loads(row['asset'])
        return row



    
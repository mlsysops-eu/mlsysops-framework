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

import importlib
import os
import time
import traceback
from copy import deepcopy

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import asyncio

import mlsysops
import mlsysops.tasks.analyze as AnalyzeClass
from ..data.state import MLSState
from ..policy import Policy
from ..logger_util import logger

from enum import Enum


class PolicyScopes(Enum):
    APPLICATION = "application"
    GLOBAL = "global"


class FileEvents(Enum):
    CREATED = 0
    MODIFIED = 1
    DELETED = 2


class PolicyController:
    _instance = None
    __initialized = False  # Tracks whether __init__ has already run
    state = None
    agent = None
    active_policies = {"global" : {}, "application": {}}
    observer = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(PolicyController, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def init(self,agent, state: MLSState):
        if not self.__initialized:
            self.__initialized = True
            self.state = state
            self.agent = agent
        return self._instance

    def get_policy_instance(self, scope: str, id: str, policy_name: str = None ):
        """
        Retrieves a specific policy instance based on the given scope and ID.

        Args:
            scope (PolicyScopes): The scope of the policy to be retrieved.
            id: The unique identifier associated with the policy within the given scope.

        Returns:
            The policy instance corresponding to the provided scope and ID if found.
            None if no matching policy exists or an error occurs.
        """
        try:
            # logger.debug(f"Getting policy instance for scope: {scope} and id: {id} name {policy_name}")
            if policy_name is None: # analyze calls
                if scope == PolicyScopes.APPLICATION.value:
                   return self.active_policies[scope][id].items()
                elif scope == PolicyScopes.GLOBAL.value:
                    object_to_return = {id: self.active_policies[scope][id]}
                    return object_to_return.items()
                else:
                    return None
            else: # plan calls
                if id != policy_name:
                    return {policy_name: self.active_policies[scope][id][policy_name]}
                else:
                    return self.active_policies[scope][policy_name]
        except Exception as e:
            logger.error(f"Invalid policy instance: {e}")
            logger.error(f"active_policies {traceback.format_exc()}")
            return None

    async def start_global_policies(self):
        logger.debug(f"Starting Global Policies {self.state.policies}")

        for policy_template in self.state.policies.values():
            if policy_template.scope == PolicyScopes.GLOBAL.value:
                new_policy_object = policy_template.clone()
                new_policy_object.load_module()
                new_policy_object.initialize(self.agent)
                # TODO put some check, if the policies handle mechanism that are not available
                new_analyze_task = AnalyzeClass.AnalyzeTask(
                    id=new_policy_object.name,
                    state=self.state,
                    scope=new_policy_object.scope)
                asyncio.create_task(new_analyze_task.run())

                # there should one instance of this policy, with its corresponding analyze task
                self.active_policies[PolicyScopes.GLOBAL.value][new_policy_object.name] = new_policy_object

    async def start_application_policies(self,application_id):
        logger.debug(f"Starting Application Policies {self.state.policies}")
        try:
            for policy_template in self.state.policies.values():
                logger.debug(f"Policy template: {policy_template.name} ---- scope {policy_template.scope} ---- application_id {application_id} ----")
                if policy_template.scope == PolicyScopes.APPLICATION.value:
                    new_policy_object = policy_template.clone()
                    new_policy_object.load_module()
                    new_policy_object.initialize(self.agent)
                    if not self.active_policies[PolicyScopes.APPLICATION.value].get(application_id):
                        self.active_policies[PolicyScopes.APPLICATION.value][application_id] = {}

                    self.active_policies[PolicyScopes.APPLICATION.value][application_id][new_policy_object.name] = new_policy_object
                    logger.debug(f"Started Application Policy {new_policy_object.name}")
        except Exception as e:
            logger.error(f"Error while starting application policies: {e}")

    async def delete_application_policies(self, application_id):
        """
        Deletes all active application policies for the given application ID.

        Args:
            application_id (str): The ID of the application whose policies should be deleted.

        Returns:
            bool: True if policies were successfully deleted, False if no policies existed for the given application ID.
        """
        logger.debug(f"Deleting Application Policies for application_id: {application_id}")

        # Check if the application has any active policies
        if application_id in self.active_policies[PolicyScopes.APPLICATION.value]:
            # update possible telemetry changes
            for policyname in self.active_policies[PolicyScopes.APPLICATION.value][application_id].keys():
                await self.agent.telemetry_controller.remove_interval(policyname)
            # Remove the application-specific policies
            del self.active_policies[PolicyScopes.APPLICATION.value][application_id]
            logger.info(f"Deleted Application Policies for application_id: {application_id}")
            return True
        else:
            logger.warning(f"No Application Policies found for application_id: {application_id}")
            return False

    async def load_policy_modules(self):
        """
        Lists all .py files in the given directory with prefix 'policy-', extracts the
        string between '-' and '.py', loads the Python module, and verifies
        the presence of expected methods (initialize, initial_plan, analyze, re_plan).

        Args:
            directory (str): Path to the directory containing the .py files.

        Returns:
            dict: A dictionary where keys are the extracted strings (policy names)
                  and values are the loaded modules.
        """
        try:
            directory = self.state.configuration.policy_directory
            # List all files in the directory
            for filename in os.listdir(directory):
                # Check for files matching the pattern 'policy-*.py'
                if filename.startswith("policy-") and filename.endswith(".py"):
                    # Extract the policy name (string between '-' and '.py')
                    policy_name = filename.split('-')[1].rsplit('.py', 1)[0]

                    # Construct the full file path
                    file_path = os.path.join(directory, filename)

                    policy_object = Policy(policy_name, file_path)
                    policy_object.load_module()
                    policy_object.validate()
                    policy_object.initialize(self.agent)

                    # Add the policy in the module
                    self.state.add_policy(policy_name,policy_object) # add the global policies as templates

                    logger.info(f"Loaded module {policy_name} from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load policy modules: {e}")

    async def load_core_policy_modules(self):
        """
        Lists all .py files in the core policy directory with prefix 'policy-',
        extracts the continuum level and the policy name from the name, loads the Python module, and verifies
        the presence of expected methods (initialize, initial_plan, analyze, re_plan).

        Args:
            directory (str): Path to the directory containing the .py files.

        Returns:
            dict: A dictionary where keys are the extracted strings (policy names)
                  and values are the loaded modules.
        """
        try:
            directory = os.path.join(os.path.dirname(mlsysops.__file__), "policies")
            # List all files in the directory
            for filename in os.listdir(directory):
                # Check for files matching the pattern 'policy-*.py'
                if filename.startswith("policy-") and filename.endswith(".py"):
                    # Extract the policy name (string between '-' and '.py')
                    policy_name = filename.split('-')[2].rsplit('.py', 1)[0]
                    continuum_level = filename.split('-')[1].rsplit('.py', 1)[0]

                    if self.state.configuration.continuum_layer != continuum_level:
                        continue # skip the policy not intended for this layer

                    if self.state.policy_exists(policy_name):
                        continue # policy is overridden by a user/custom policy

                    # Construct the full file path
                    file_path = os.path.join(directory, filename)

                    policy_object = Policy(policy_name, file_path, core=True)
                    policy_object.load_module()
                    policy_object.validate()
                    policy_object.initialize(self.agent)

                    # Add the policy in the module
                    self.state.add_policy(policy_name, policy_object) # add the global policies as templates

                    logger.info(f"Loaded core policy module {policy_name} from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load core policy modules: {e}")

    def handle_policy_change(self,file_path: str, event: FileEvents):
        filename = os.path.basename(file_path)
        if filename.startswith("policy-") and filename.endswith(".py"):
            policy_name = filename.split('-')[1].rsplit('.py', 1)[0]
            match event:
                case FileEvents.CREATED:
                    try:
                        policy_object = Policy(policy_name, file_path)
                        policy_object.load_module()
                        policy_object.validate()
                        policy_object.initialize(self.agent)

                        # Add the policy in the module
                        self.state.add_policy(policy_name, policy_object)  # add the global policies as templates

                        # activate the policy
                        new_policy_object = policy_object.clone()
                        new_policy_object.load_module()
                        new_policy_object.initialize(self.agent)

                        if new_policy_object.scope == PolicyScopes.GLOBAL.value:
                            new_analyze_task = AnalyzeClass.AnalyzeTask(
                                id=new_policy_object.name,
                                state=self.state,
                                scope=new_policy_object.scope)
                            asyncio.create_task(new_analyze_task.run())

                            # there should one instance of this policy, with its corresponding analyze task
                            self.active_policies[PolicyScopes.GLOBAL.value][new_policy_object.name] = new_policy_object

                        if new_policy_object.scope == PolicyScopes.APPLICATION.value:
                            for running_application_id in self.active_policies[PolicyScopes.APPLICATION.value].keys():
                                self.active_policies[PolicyScopes.APPLICATION.value][running_application_id][
                                    new_policy_object.name] = new_policy_object

                                logger.debug(f"Started new Application Policy {new_policy_object.name}")
                        logger.info(f"Loaded new policy from file: {policy_name} {file_path}")
                    except Exception as e:
                        logger.error(f"Error creating new policy from file change {e}")
                case FileEvents.MODIFIED:
                    logger.info(f"------------------Policy change detected in file: {filename} (policy_name: {policy_name})")
                    # Reload the policy modules and update the internal structure
                    try:
                        for scope in [PolicyScopes.GLOBAL.value, PolicyScopes.APPLICATION.value]:
                            for key, policy_objects in self.active_policies[scope].items():
                                for policy_key, policy_object in policy_objects.items():
                                    if policy_object.name == policy_name:
                                        policy_object.load_module()
                                        policy_object.validate()
                                        policy_object.initialize(self.agent)
                                        logger.info(f"Reloaded module application {policy_name}")
                    except Exception as e:
                        logger.error(f"Error while reloading policy modules: {e}")
                case FileEvents.DELETED:
                        logger.info(f"------------------Policy deleted: {filename} (policy_name: {policy_name})")

                        # Reload the policy modules and update the internal structure
                        try:
                            for scope in [PolicyScopes.GLOBAL.value, PolicyScopes.APPLICATION.value]:
                                active_policies_keys = self.active_policies[scope].items()
                                for key, policy_objects in active_policies_keys:
                                    temp_policy_objects = list(policy_objects.keys())
                                    for policy_key in temp_policy_objects:
                                        if policy_key == policy_name:
                                            # update telemetry
                                            self.agent.current_loop.create_task(
                                                self.agent.telemetry_controller.remove_interval(policy_name))
                                            # Remove the application-specific policies
                                            if scope == PolicyScopes.APPLICATION.value:
                                                del self.active_policies[scope][key][policy_key]
                                            else:
                                                del self.active_policies[scope][policy_key]
                                            logger.info(
                                                f"Deleted Policy {policy_name} for scope {scope} and key {policy_key}")
                                            # remove template
                            self.state.remove_policy(policy_name)
                        except Exception as e:
                            logger.error(f"Error while deleting policy modules: {e}")
                            logger.error(traceback.format_exc())

    def start_policy_directory_monitor(self):
        """
        Starts the directory monitoring process in the background.
        This method is non-blocking and leaves the observer running.
        """
        directory = self.state.configuration.policy_directory

        # Set up the event handler and observer
        event_handler = PolicyDirectoryHandler(callback=self.handle_policy_change)
        self.observer = Observer()
        self.observer.schedule(event_handler, directory, recursive=False)

        # Start the observer in the background (non-blocking)
        self.observer.start()
        logger.info(f"Started monitoring the policy directory: {directory}")

    def stop_policy_directory_monitor(self):
        """
        Stops the directory monitoring process gracefully.
        Ensures the observer is properly stopped and cleaned up.
        """
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Policy directory monitor stopped successfully.")

class PolicyDirectoryHandler(FileSystemEventHandler):
    """
    Handler class to process file system events and trigger a callback.
    """
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_modified(self, event):
        if not event.is_directory:
            self.callback(event.src_path, FileEvents.MODIFIED)

    def on_created(self, event):
        if not event.is_directory:
            self.callback(event.src_path, FileEvents.CREATED)

    def on_deleted(self, event):
        if not event.is_directory:
            self.callback(event.src_path, FileEvents.DELETED)

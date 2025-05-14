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

import asyncio

import mlsysops.tasks.analyze as AnalyzeClass
from ..data.state import MLSState
from ..policy import Policy
from ..logger_util import logger

from enum import Enum


class PolicyScopes(Enum):
    APPLICATION = "application"
    GLOBAL = "global"


class PolicyController:
    _instance = None
    __initialized = False  # Tracks whether __init__ has already run
    state = None
    active_policies = {"global" : {}, "application": {}}

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(PolicyController, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def init(self,state: MLSState):
        if not self.__initialized:
            self.__initialized = True
            self.state = state
        return self._instance

    def get_policy_for_application(self,application_id):
        for policy in self.state.policies:
            # development - always fetch the first one loaded
            logger.debug(f"returning policy {policy.name}")
            return policy
        return None

    def get_policy_instance(self, scope: str, id: str ):
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
            logger.debug(f"Getting policy instance for scope: {scope} and id: {id} list {self.active_policies[scope]}")
            return self.active_policies[scope][id]
        except Exception as e:
            logger.error(f"Invalid policy instance: {e}")
            return None

    def start_global_policies(self):
        logger.debug(f"Starting Global Policies {self.state.policies}")

        for policy_template in self.state.policies:
            if policy_template.scope == PolicyScopes.GLOBAL.value:
                print("Got  global for ", policy_template)
                new_policy_object = policy_template.clone()
                new_policy_object.load_module()
                new_policy_object.initialize()
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

        for policy_template in self.state.policies:
            if policy_template.scope == PolicyScopes.APPLICATION.value:
                new_policy_object = policy_template.clone()
                new_policy_object.load_module()
                new_policy_object.initialize()
                logger.debug(f"-----------------> {self.active_policies[PolicyScopes.APPLICATION.value]}")
                if not self.active_policies[PolicyScopes.APPLICATION.value].get(application_id):
                    self.active_policies[PolicyScopes.APPLICATION.value][application_id] = {}

                self.active_policies[PolicyScopes.APPLICATION.value][application_id][new_policy_object.name] = new_policy_object
                logger.debug(f"Started Application Policy {new_policy_object.name}")


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
            # Remove the application-specific policies
            del self.active_policies[PolicyScopes.APPLICATION.value][application_id]
            logger.info(f"Deleted Application Policies for application_id: {application_id}")
            return True
        else:
            logger.warning(f"No Application Policies found for application_id: {application_id}")
            return False

    def load_policy_modules(self):
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
                policy_object.initialize()
                print(policy_object.module)
                # policy_object.module = None

                # Add the policy in the module
                self.state.add_policy(policy_object) # add the global policies as templates

                logger.info(f"Loaded module {policy_name} from {file_path}")




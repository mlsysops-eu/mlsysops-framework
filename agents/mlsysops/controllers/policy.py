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

from mlsysops.data.state import MLSState
from mlsysops.policy import Policy

from mlsysops.logger_util import logger


class PolicyController:
    _instance = None
    __initialized = False  # Tracks whether __init__ has already run

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

                # Dynamically import the policy module
                spec = importlib.util.spec_from_file_location(policy_name, file_path)
                module = importlib.util.module_from_spec(spec)

                try:
                    # Load the module
                    spec.loader.exec_module(module)

                    # Verify required methods exist in the module
                    required_methods = ['initialize', 'analyze', 'plan']
                    for method in required_methods:
                        if not hasattr(module, method):
                            raise AttributeError(f"Module {policy_name} is missing required method: {method}")

                    # Add the policy in the module
                    self.state.add_policy(Policy(policy_name, module))

                    logger.info(f"Loaded module {policy_name} from {file_path}")

                except Exception as e:
                    logger.error(f"Failed to load module {policy_name} from {file_path}: {e}")
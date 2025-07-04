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

from mlsysops.data.state import MLSState
from mlsysops.logger_util import logger


class MechanismsController:
    _instance = None
    __initialized = False  # Tracks whether __init__ has already run
    _state: MLSState
    queues = {}

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MechanismsController, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def init(self,state: MLSState):
        if not self.__initialized:
            self.__initialized = True
            self._state = state
        return self._instance

    def get_enabled_mechanisms(self,application_id):
        for policy in self._state.policies:
            # development - always fetch the first one loaded
            logger.debug(f"returning policy {policy.name}")
            return policy

    def is_mechanism_enabled(self,mechanism_name):
        if mechanism_name in self._state.active_mechanisms:
            return True
        else:
            return False

    def load_mechanisms_modules(self, agent_state):
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
        directory = self._state.configuration.mechanisms_directory
        # List all files in the directory
        for filename in os.listdir(directory):
            if filename.endswith(".py"):
                # Extract the policy name (string between '-' and '.py')
                mechanism_name = filename.rsplit('.py', 1)[0]

                # check if the mechanism is activated
                if mechanism_name not in  self._state.configuration.mechanisms:
                    continue

                # Construct the full file path
                file_path = os.path.join(directory, filename)

                # Dynamically import the policy module
                spec = importlib.util.spec_from_file_location(mechanism_name, file_path)
                module = importlib.util.module_from_spec(spec)

                try:
                    # Load the module
                    spec.loader.exec_module(module)

                    # Verify required methods exist in the module
                    required_methods = ['initialize','apply', 'get_options', 'get_state']
                    for method in required_methods:
                        if not hasattr(module, method):
                            raise AttributeError(f"Module {mechanism_name} is missing required method: {method}")

                    # Add the policy in the module
                    self._state.active_mechanisms[mechanism_name] = {
                        "module" : module,
                        "state" : None,
                        "options": None,
                    }

                    logger.info(f"Loaded module {mechanism_name} from {file_path}, calling initialize")

                    # create two queues
                    self.queues[mechanism_name] = {
                        "inbound": asyncio.Queue(),
                        "outbound": asyncio.Queue(),
                    }
                    self._state.active_mechanisms[mechanism_name]["module"].initialize(
                        inbound_queue=self.queues[mechanism_name]["inbound"],
                        outbound_queue=self.queues[mechanism_name]["outbound"],agent_state=agent_state)
                    self._state.active_mechanisms[mechanism_name]["state"] = self._state.active_mechanisms[mechanism_name]["module"].get_state()
                    self._state.active_mechanisms[mechanism_name]["options"] = self._state.active_mechanisms[mechanism_name]["module"].get_options()

                    logger.debug(f"{self._state.active_mechanisms[mechanism_name]}")
                except Exception as e:
                    logger.error(f"Failed to load module {mechanism_name} from {file_path}: {e}")
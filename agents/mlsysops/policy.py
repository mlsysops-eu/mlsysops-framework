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
import copy
import sys

from .logger_util import logger

class Policy:
    def __init__(self, name, module_path):
        self.name = name
        self.module_path = module_path
        self.module = None
        self.context = None
        self.current_plan = None
        self.scope = None
        self.core = False

    def initialize(self):
        # Check if it was initialized
        try:
            if self.context is None:
                self.context = self.module.initialize()
                logger.debug(f"Policy {self.name} initialized {self.context}")
                self.scope = self.context['scope']
                self.core = self.context['core']
        except Exception as e:
            logger.error(f"Failed to initialize policy {self.name}: {e}")

    def update_context(self,context):
        self.context = context

    def analyze(self,application_description, system_description, current_plan, telemetry, ml_connector):
        # Inject context before calling module method
        analyze_result,updated_context = self.module.analyze(self.context,application_description, system_description, current_plan, telemetry, ml_connector)
        self.update_context(updated_context)
        return analyze_result

    def plan(self,application_description, system_description, current_plan, telemetry, ml_connector,available_assets):
        # Inject context before calling module method
        new_plan, updated_context = self.module.plan(self.context,application_description, system_description, self.current_plan, telemetry, ml_connector,available_assets)
        self.update_context(updated_context)
        self.current_plan = new_plan
        return new_plan

    def load_module(self):
        # Dynamically import the policy module
        try:
            if self.name in sys.modules:
               del sys.modules[self.name]
            spec = importlib.util.spec_from_file_location(self.name, self.module_path)
            self.module = importlib.util.module_from_spec(spec)
            # Load the module
            spec.loader.exec_module(self.module)
        except Exception as e:
            logger.error(f"Failed to load module {self.name} from {self.module_path}: {e}")

    def validate(self):
        try:
            if self.module is None:
                self.load_module()

            # Verify required methods exist in the module
            required_methods = ['initialize', 'analyze', 'plan']
            for method in required_methods:
                if not hasattr(self.module, method):
                    raise AttributeError(f"Module {self.name} is missing required method: {method}")
        except Exception as e:
            logger.error(f"Failed to load module {self.name} from {self.module_path}: {e}")


    # New method to be added to the Policy class
    def clone(self):
        """
        Create a deep independent copy of the Policy instance and return it.
        """
        try:
            print(f"Cloning {self.name} {self.module}")
            return copy.deepcopy(self)
        except Exception as e:
            logger.error(f"Failed to clone policy {self.name}: {e}")
            return None

    def __getstate__(self):
        """
        Customize the picklable state of the object.
        Exclude the 'module' attribute from serialization.
        """
        state = self.__dict__.copy()
        # Remove the module from the state to exclude it from serialization
        if "module" in state:
            del state["module"]
        return state

    def __setstate__(self, state):
        """
        Customize how the object's state is restored during deserialization.
        """
        self.__dict__.update(state)
        # Re-initialize excluded attributes if necessary
        self.module = None
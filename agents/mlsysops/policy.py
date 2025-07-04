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
import subprocess
import sys
import time
import ast

import asyncio

from .logger_util import logger

class Policy:
    def __init__(self, name, module_path, core=False):
        self.name = name
        self.module_path = module_path
        self.module = None
        self.context = {}
        self.scope = None
        self.core = core
        self.last_analyze_run = time.time()

    def initialize(self, agent):
        # Check if it was initialized
        try:
            policy_initial_context = self.module.initialize().copy()
            self.context.update(policy_initial_context)

            # Add telemetry metrics
            telemetry = policy_initial_context.get("telemetry", {})
            telemetry_metrics = telemetry.get("metrics", [])

            for metric_name in telemetry_metrics:
                if metric_name:
                    agent.current_loop.create_task(agent.monitor_task.add_metric(metric_name))

            # Configure telemetry with the scrape interval
            scrape_interval = telemetry.get("system_scrape_interval")
            if scrape_interval:
                agent.current_loop.create_task(agent.telemetry_controller.add_new_interval(self.name,scrape_interval))

            logger.debug(f"Policy {self.name} initialized {self.context}")
            self.scope = self.context['scope']
        except Exception as e:
            logger.error(f"Failed to initialize policy {self.name}: {e}")

    def update_context(self,context):
        self.context = context

    def get_analyze_period_from_context(self):
        return self.context['configuration']['analyze_interval']

    async def analyze(self,application_description, system_description, mechanisms, telemetry, ml_connector):
        # Inject context before calling module method
        try:
            analyze_result,updated_context = await self.module.analyze(self.context,application_description, system_description, mechanisms, telemetry, ml_connector)
        except Exception as e:
            logger.error(f"Error in policy analyze {self.name}: {e}")
            return False
        self.update_context(updated_context)
        self.last_analyze_run = time.time()
        return analyze_result

    async def plan(self,application_description, system_description, mechanisms, telemetry, ml_connector):
        # Inject context before calling module method
        try:
            new_plan, updated_context = await self.module.plan(self.context,application_description, system_description, mechanisms, telemetry, ml_connector)
        except Exception as e:
            logger.error(f"Error in policy plan {self.name}: {e}")
            return {}
        self.update_context(updated_context)
        return new_plan

    def load_module(self):
        # Dynamically import the policy module
        try:
            packages = self.parse_module_for_context_data()
            if packages and isinstance(packages, list):
                for pkg in packages:
                    if isinstance(pkg, str):
                        logger.debug(f"Installing package: {pkg}")
                        try:
                            # Install the package using subprocess
                            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                        except subprocess.CalledProcessError as e:
                            logger.error(f"Failed to install package {pkg}: {e}")
                    else:
                        logger.warning(f"Invalid package format: {pkg}. Expected a string.")
            else:
                logger.info("No packages to install or 'packages' is not a valid list.")

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

    def parse_module_for_context_data(self):
        """Parses the Python module to extract static 'context' definitions."""
        try:
            # Read the module file
            with open(self.module_path, 'r') as f:
                module_code = f.read()

            # Parse the Python code
            tree = ast.parse(module_code)

            # Look for the 'context' variable in the module
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):  # Look for assignment statements
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "initialContext":
                            # Extract the value of the 'context' variable
                            context_value = ast.literal_eval(node.value)  # Convert AST to Python objects
                            if isinstance(context_value, dict) and 'packages' in context_value:
                                return context_value.get('packages', [])

            logger.warning(f"No 'context' variable found in {self.module_path} or 'packages' key is missing.")
            return []

        except Exception as e:
            logger.error(f"Failed to parse module {self.module_path} for 'context': {e}")
            return []

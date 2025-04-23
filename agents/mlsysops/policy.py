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

from .logger_util import logger

class Policy:
    def __init__(self, name, module):
        self.name = name
        self.module = module
        self.context = None
        self.current_plan = None
        self.initialize()

    def initialize(self):
        # Check if it was initialized
        if self.context is None:
            logger.debug(f"Initializing policy {self.name}")
            self.context = self.module.initialize()
            logger.debug(f"Policy {self.name} initialized {self.context}")

    def update_context(self,context):
        self.context = context

    # Inject context before calling module method
    def analyze(self,application_description, system_description, current_plan, telemetry, ml_connector):
        analyze_result,updated_context = self.module.analyze(self.context,application_description, system_description, current_plan, telemetry, ml_connector)
        self.update_context(updated_context)
        return analyze_result

    def plan(self,application_description, system_description, current_plan, telemetry, ml_connector,available_assets):
        new_plan, updated_context = self.module.plan(self.context,application_description, system_description, self.current_plan, telemetry, ml_connector,available_assets)
        self.update_context(updated_context)
        self.current_plan = new_plan
        return new_plan
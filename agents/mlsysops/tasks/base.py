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
import os


class BaseTask:
    def __init__(self, state):
        self.state = state

    def get_telemetry_argument(self):
        argument = {
            "endpoint": "localhost:9100/metrics",
            "data": self.state.monitor_data
        }

        return argument

    def get_system_description_argument(self):
        return self.state.configuration.system_description

    def get_available_assets(self):
        return self.state.configuration.mechanisms

    def get_assets(self):
        return self.state.assets

    def get_ml_connector_object(self):
        return os.getenv("MLS_MLCONNECTOR_ENDPOINT")
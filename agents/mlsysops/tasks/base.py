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

from mlsysops.logger_util import logger


class BaseTask:
    def __init__(self, state):
        self.state = state

    async def get_telemetry_argument(self):
        argument = {
            "prometheus_endpoint": os.getenv("LOCAL_OTEL_ENDPOINT","localhost:9100/metrics"),
            "grafana_endpoint": os.getenv("GRAFANA_ENDPOINT","localhost:3000"),
            "dataframe": await self.state.monitor_data.get_data(),
            "query": self.state.monitor_data.query_data
        }
        return argument

    def get_system_description_argument(self):
        return self.state.configuration.system_description

    def get_mechanisms(self):
        """
        Retrieve the mechanisms configured and their respective states and options.

        Returns
        -------
        dict
            A dictionary where the keys represent mechanism names, and the values are dictionaries
            containing 'state' (status of the mechanism) and 'options' (configuration options).
            If an error occurs, an empty dictionary is returned.
        """
        mechanism_dictionary = {}
        try:
            # It exposes the installed assets and the active (via configuration) assets
            mechanism_dictionary = {
                key: {
                    "state" : self.state.active_mechanisms[key]['module'].get_state(),
                    "options": self.state.active_mechanisms[key]['module'].get_options()
                }
                for key in self.state.active_mechanisms
                if key in self.state.configuration.mechanisms
            }
        except Exception as e:
            logger.error(f"Error getting mechanisms: {e}")
        finally:
            return mechanism_dictionary

    def get_ml_connector_object(self):
        return os.getenv("MLS_MLCONNECTOR_ENDPOINT")
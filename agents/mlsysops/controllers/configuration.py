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
import yaml

from dotenv import load_dotenv
import os

from mlsysops.data.configuration import AgentConfig

from mlsysops.logger_util import logger

from mlsysops.data.state import MLSState


class ConfigurationController:
    """
    Manages the application configuration,
    including loading, updating, and saving.
    """

    def __init__(self, agent_state: MLSState):
        """
        Initializes the ConfigManager.

        :param config_path: The path to the YAML configuration file.
        """
        # Load environment variables from the .env file
        load_dotenv()

        config_path = os.getenv("CONFIG_PATH", "config.yaml")

        logger.info(f"Using configuration file: {config_path}")

        self.config_path = config_path
        self.agent_state = agent_state
        self.agent_state.configuration = AgentConfig()
        self.load_config()

    def load_config(self) -> AgentConfig:
        """
        Loads the configuration from the YAML file into the AppConfig dataclass.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file '{self.config_path}' not found.")

        with open(self.config_path, "r") as file:
            data = yaml.safe_load(file)

        # Update dataclass with parsed values
        for key, value in data.items():
            if hasattr(self.agent_state.configuration, key):
                setattr(self.agent_state.configuration, key, value)
        self.agent_state.configuration.__post_init__()  # Recalculate derived fields

        logger.debug(f"Configuration file loaded. Agent configured")

    def save_config(self):
        """
        Saves the current configuration to the YAML file.
        """
        with open(self.config_path, "w") as file:
            yaml.safe_dump(self.agent_state.configuration.__dict__, file, default_flow_style=False)

    def update_config(self, **kwargs):
        """
        Updates the in-memory configuration and writes it back to the YAML file.
        :param kwargs: Key-value pairs to update.
        """
        self.agent_state.configuration.update(**kwargs)
        self.save_config()

    def get_config(self) -> AgentConfig:
        """
        Returns the current configuration.
        
        :return: The current AppConfig instance.
        """
        return self.agent_state.configuration

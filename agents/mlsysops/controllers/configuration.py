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
import socket

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
        mlsysops_path = os.path.join(os.getenv("MLSYSOPS_INSTALL_PATH","/etc/mlsysops"))

        if not os.path.exists(mlsysops_path):
            try:
                # Create the directory
                os.makedirs(mlsysops_path)
                os.makedirs(mlsysops_path+"/config")
                os.makedirs(mlsysops_path+"/descriptions")
                os.makedirs(mlsysops_path+"/policies")
                os.makedirs(mlsysops_path+"/kubeconfigs")
                os.makedirs(mlsysops_path+"/logs")
                logger.info(f"Directory {mlsysops_path} created successfully.")
            except PermissionError:
                logger.error(f"Permission denied: Unable to create {mlsysops_path}. Run as root or check permissions.")
            except Exception as e:
                logger.error(f"An error occurred while creating {mlsysops_path}: {e}")
        else:
            logger.info(f"Directory {mlsysops_path} already exists.")

        self.config_path = os.getenv("CONFIG_PATH", f"{mlsysops_path}/config/{os.getenv('NODE_NAME',socket.gethostname())}-config.yaml")
        self.description_path = os.getenv("DESCRIPTION_PATH", f"{mlsysops_path}/descriptions")
        logger.info(f"Using configuration file: {self.config_path}")

        self.agent_state = agent_state
        self.agent_state.configuration = AgentConfig()
        self.load_config()
        self.load_system_description()

    def load_config(self) -> AgentConfig:
        """
        Loads the configuration from the YAML file into the AppConfig dataclass.
        """
        if not os.path.exists(self.config_path):
            logger.debug(f"Configuration file '{self.config_path}' not found, fallback to default values.")
            self.config_path = "config.yaml"

        with open(self.config_path, "r") as file:
            data = yaml.safe_load(file)
            logger.debug(f"Configuration file '{self.config_path}' loaded.")


        # Update dataclass with parsed values
        for key, value in data.items():
            if hasattr(self.agent_state.configuration, key):
                setattr(self.agent_state.configuration, key, value)
        self.agent_state.configuration.__post_init__()  # Recalculate derived fields

    def load_system_description(self) -> AgentConfig:
        """
        Loads the system description file for the agent configuration. The system
        description file is expected to be a YAML file, and its location is determined
        based on the provided description path and the system's node name.

        Attributes:
            description_path: str
                Path to the folder where the system description YAML file is located.

        Raises:
            Exception
                If the system description file cannot be loaded due to any error.

        Returns:
            AgentConfig
                Updated configuration containing the loaded system description.
        """
        if not os.path.exists(self.description_path):
            logger.error(f"System description file '{self.description_path}' not found.")

        try :
            description_file_path = os.path.join(self.description_path, f"{self.agent_state.configuration.node}.yaml")
            with open(description_file_path, "r") as file:
                data = yaml.safe_load(file)
                self.agent_state.configuration.system_description = data
                if self.agent_state.configuration.continuum_layer in ['node', 'cluster']:
                    self.agent_state.configuration.cluster = data[f'MLSysOps{self.agent_state.configuration.continuum_layer.capitalize()}']['cluster_id']
                else:
                    self.agent_state.configuration.cluster = self.agent_state.configuration.node
            logger.debug(f"System description file loaded: {description_file_path}")
        except Exception as e:
            logger.error(f"Error loading system description file: {e}")

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

    def get_system_description(self) -> dict:
        """
        Retrieve the system description from the configuration.

        This method accesses the system configuration to extract and return
        a detailed description of the system. It is intended to provide
        system-related metadata or information.

        Returns:
            dict: A dictionary containing the detailed system description.
        """
        return self.get_config().system_description

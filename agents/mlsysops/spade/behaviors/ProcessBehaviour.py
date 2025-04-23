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

import asyncio
import json
import os
import subprocess
import time
from ...logger_util import logger
import yaml
from spade.behaviour import CyclicBehaviour


def create_yaml_file(yaml_string, output_file):
    # Write the YAML string to a file
    with open(output_file, 'w') as file:
        file.write(yaml_string)


def transform_description(input_dict):
    # Extract the name and other fields under "MLSysOpsApplication"
    ml_sys_ops_data = input_dict.pop("MLSysOpsApplication", {})
    app_name = ml_sys_ops_data.pop("name", "")

    # Create a new dictionary with the desired structure
    updated_dict = {
        "apiVersion": "fluidity.gr/v1",
        "kind": "MLSysOpsApp",
        "metadata": {
            "name": app_name
        }
    }

    # Merge the remaining fields from MLSysOpsApplication into the updated dictionary
    updated_dict.update(ml_sys_ops_data)

    # Convert the updated dictionary to a YAML-formatted string
    yaml_output = yaml.dump(updated_dict, default_flow_style=False)

    return yaml_output


def apply_kubectl(file_path, command='apply'):
    """
    Apply a Kubernetes configuration file using kubectl.

    :param command:
    :param file_path: Path to the Kubernetes configuration file.
    """
    try:
        env_vars = os.environ.copy()
        result = subprocess.run(["kubectl", command, "-f", file_path], check=True, text=True, capture_output=True,
                                env=env_vars)

        # demo_telemetry_with_delay(command)
        print(f"Command {command} executed successfully: {result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error executing kubectl command: {e.stderr}")


class ProcessBehaviour(CyclicBehaviour):
    """
          A behavior that processes tasks from a Redis queue in a cyclic manner.
    """

    def __init__(self, redis_manager):
        super().__init__()
        self.r = redis_manager

    async def run(self):
        """Continuously process tasks from the Redis queue."""
        logger.info("MLs Agent is processing for Application ...")

        if self.r.is_empty(self.r.q_name):
            print(self.r.q_name + " queue is empty waiting for next iteration ")
            await asyncio.sleep(10)
        else:
            q_info = self.r.pop(self.r.q_name)
            data_dict = json.loads(q_info)
            app_id = data_dict['MLSysOpsApplication']['name']
            print("name", app_id, type(app_id))
            print(self.r.get_dict_value("system_app_hash", app_id))

            if self.r.get_dict_value("system_app_hash", app_id) == "To_be_removed":
                file = transform_description(data_dict)
                output_file = f"CR-{app_id}.yaml"
                create_yaml_file(file, output_file)
                apply_kubectl(output_file, "delete")
                self.r.update_dict_value("system_app_hash", app_id, "Removed")

                time.sleep(5)
                self.r.remove_key("system_app_hash", app_id)

            else:

                self.r.update_dict_value("system_app_hash", app_id, "Under_deployment")
                file = transform_description(data_dict)
                output_file = f"CR-{app_id}.yaml"
                create_yaml_file(file, output_file)
                apply_kubectl(output_file)
                self.r.update_dict_value("system_app_hash", app_id, "Deployed")

                await asyncio.sleep(2)

            await asyncio.sleep(10)

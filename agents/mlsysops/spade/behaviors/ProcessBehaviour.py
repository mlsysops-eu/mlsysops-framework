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
import kubernetes_asyncio
from kubernetes_asyncio.client.api import CustomObjectsApi
from kubernetes_asyncio.client import ApiException
from ruamel.yaml import YAML


def transform_description(input_dict):
    # Extract the name and other fields under "MLSysOpsApplication"
    ml_sys_ops_data = input_dict.pop("MLSysOpsApplication", {})
    app_name = ml_sys_ops_data.pop("name", "")

    # Create a new dictionary with the desired structure
    updated_dict = {
        "name": app_name
    }

    # Merge the remaining fields from MLSysOpsApplication into the updated dictionary
    updated_dict.update(ml_sys_ops_data)

    # Convert the updated dictionary to a YAML-formatted string
    yaml_output = yaml.dump(updated_dict, default_flow_style=False)

    return updated_dict


class ProcessBehaviour(CyclicBehaviour):
    """
          A behavior that processes tasks from a Redis queue in a cyclic manner.
    """

    def __init__(self, redis_manager, message_queue):
        super().__init__()
        self.r = redis_manager
        self.message_queue = message_queue

    async def run(self):
        """Continuously process tasks from the Redis queue."""
        logger.info("MLs Agent is processing for Application ...")

        if self.r.is_empty(self.r.q_name):
            logger.debug(self.r.q_name + " queue is empty, waiting for next iteration...")
            await asyncio.sleep(10)
            return

        q_info = self.r.pop(self.r.q_name)
        data_dict = json.loads(q_info)
        app_id = data_dict['MLSysOpsApp']['name']
        logger.debug(self.r.get_dict_value("system_app_hash", app_id))

        group = "mlsysops.eu"
        version = "v1"
        plural = "mlsysopsapps"
        namespace = "default"
        name = app_id

        if self.r.get_dict_value("system_app_hash", app_id) == "To_be_removed":
            try:
                # Delete the existing custom resource
                logger.info(f"Deleting Custom Resource: {name}")
                # SEND MESSAGE TO THE QUEUE
                await self.message_queue.put({
                    "event": "application_removed",
                    "payload": data_dict
                }
                )

                logger.info(f"Custom Resource '{name}' deleted successfully.")
                self.r.update_dict_value("system_app_hash", app_id, "Removed")
                self.r.remove_key("system_app_hash", app_id)

            except ApiException as e:
                if e.status == 404:
                    logger.warning(f"Custom Resource '{name}' not found. Skipping deletion.")
                else:
                    logger.error(f"Error deleting Custom Resource '{name}': {e}")
                    raise
        else:

            try:

                # SEND MESSAGE TO THE QUEUE

                self.r.update_dict_value("system_app_hash", app_id, "Under_deployment")

                await self.message_queue.put(
                    {
                        "event": "application_submitted",
                        "payload": data_dict
                    }
                )

                self.r.update_dict_value("system_app_hash", app_id, "Deployed")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error during deployment of '{name}': {e}")
                self.r.update_dict_value("system_app_hash", app_id, "Deployment_Failed")

        await asyncio.sleep(2)

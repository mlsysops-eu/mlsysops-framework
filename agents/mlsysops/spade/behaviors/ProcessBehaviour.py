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
        "apiVersion": "mlsysops.eu/v1",
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

        karmada_api_kubeconfig = os.getenv("KARMADA_API_KUBECONFIG", "kubeconfigs/karmada-api.kubeconfig")

        try:
            await kubernetes_asyncio.config.load_kube_config(config_file=karmada_api_kubeconfig)
        except kubernetes_asyncio.config.ConfigException:
            logger.info("Running out-of-cluster configuration.")
            return

        # Initialize Kubernetes API client
        async with kubernetes_asyncio.client.ApiClient() as api_client:
            custom_api = CustomObjectsApi(api_client)

            if self.r.is_empty(self.r.q_name):
                logger.debug(self.r.q_name + " queue is empty, waiting for next iteration...")
                await asyncio.sleep(10)
                return

            q_info = self.r.pop(self.r.q_name)
            data_dict = json.loads(q_info)
            app_id = data_dict['MLSysOpsApplication']['name']
            logger.debug(f"name {app_id} {type(app_id)}")
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
                    await custom_api.delete_namespaced_custom_object(
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=plural,
                        name=name
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
                    self.r.update_dict_value("system_app_hash", app_id, "Under_deployment")
                    # Transform and parse the description
                    file_content = transform_description(data_dict)
                    yaml = YAML(typ="safe")
                    cr_spec = yaml.load(file_content)

                    # Create or update the custom resource
                    logger.info(f"Creating or updating Custom Resource: {name}")
                    try:
                        current_resource = await custom_api.get_namespaced_custom_object(
                            group=group,
                            version=version,
                            namespace=namespace,
                            plural=plural,
                            name=name
                        )
                        # Add resourceVersion for updating
                        cr_spec["metadata"]["resourceVersion"] = current_resource["metadata"]["resourceVersion"]
                        await custom_api.replace_namespaced_custom_object(
                            group=group,
                            version=version,
                            namespace=namespace,
                            plural=plural,
                            name=name,
                            body=cr_spec
                        )
                        logger.info(f"Custom Resource '{name}' updated successfully.")
                    except ApiException as e:
                        if e.status == 404:
                            # Resource does not exist; create it
                            await custom_api.create_namespaced_custom_object(
                                group=group,
                                version=version,
                                namespace=namespace,
                                plural=plural,
                                body=cr_spec
                            )
                            logger.info(f"Custom Resource '{name}' created successfully.")
                        else:
                            logger.error(f"Error processing Custom Resource: {e}")
                            raise

                    self.r.update_dict_value("system_app_hash", app_id, "Deployed")
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Error during deployment of '{name}': {e}")
                    self.r.update_dict_value("system_app_hash", app_id, "Deployment_Failed")

        await asyncio.sleep(2)


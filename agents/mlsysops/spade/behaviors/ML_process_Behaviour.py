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
import time
import yaml
from spade.behaviour import OneShotBehaviour
# Make sure to import the ML check behavior from its module.
from .Check_ml_deployment_Behaviour import Check_ml_deployment_Behaviour
from datetime import datetime

from mlstelemetry import MLSTelemetry
from ...logger_util import logger

import kubernetes_asyncio
from kubernetes_asyncio.client.api import CustomObjectsApi
from kubernetes_asyncio.client import ApiException

mlsTelemetryClient = MLSTelemetry("continuum", "agent")

os.environ['TELEMETRY_ENDPOINT'] = "karmada.mlsysops.eu:4317"

sleep_time = 1


from spade.behaviour import CyclicBehaviour

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

class ML_process_Behaviour(CyclicBehaviour):
    """
          A behavior that processes tasks from a Redis queue in a cyclic manner.
    """

    def __init__(self, redis_manager,message_queue):
        super().__init__()
        self.r = redis_manager
        self.message_queue=message_queue

    async def run(self):
        """Continuously process tasks from the Redis queue."""
        logger.debug("MLs Agent is processing for ML Deployments...")

        karmada_api_kubeconfig = os.getenv("KARMADA_API_KUBECONFIG", "kubeconfigs/karmada-api.kubeconfig")

        try:
            await kubernetes_asyncio.config.load_kube_config(config_file=karmada_api_kubeconfig)
        except kubernetes_asyncio.config.ConfigException:
            logger.error(f"Error loading karmada api config with external kubeconfig: {karmada_api_kubeconfig}")
            return

        # Initialize Kubernetes custom API client
        async with kubernetes_asyncio.client.ApiClient() as api_client:
            custom_api = CustomObjectsApi(api_client)

            if self.r.is_empty(self.r.ml_q):
                logger.debug("Queue is empty, waiting for the next iteration...")
                await asyncio.sleep(10)
                return

            q_info = self.r.pop(self.r.ml_q)
            q_info = q_info.replace("'", '"')
            print(q_info)
            data_queue = json.loads(q_info)
            if 'MLSysOpsApplication' not in data_queue:
                # probably it is removal
                print(f"fffff {data_queue.keys()}")
                for key in data_queue.keys():
                    model_id = key
            else:
                model_id = data_queue["MLSysOpsApplication"]["mlsysops-id"]
                data_queue['MLSysOpsApplication']['name'] = data_queue['MLSysOpsApplication']['name'] + "-" + model_id
                try:
                    comp_name = data_queue["MLSysOpsApplication"]["components"][0]["Component"]["name"]
                    cluster_id = data_queue["MLSysOpsApplication"]["clusterPlacement"]["clusterID"][0]

                    self.r.update_dict_value("ml_location", model_id, cluster_id)
                except KeyError:
                    cluster_id = self.r.get_dict_value("ml_location", model_id)
                    print("CLUSTER ID " + str(cluster_id))

            group = "mlsysops.eu"
            version = "v1"
            plural = "mlsysopsapps"
            namespace = "default"
            name = model_id

            if self.r.get_dict_value("endpoint_hash", model_id) == "To_be_removed":
                try:
                    # Delete the existing custom resource
                    logger.debug(f"Deleting Custom Resource: {name}")
                    await custom_api.delete_namespaced_custom_object(
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=plural,
                        name="ml-app-" + model_id
                    )
                    logger.debug(f"Custom Resource '{name}' deleted successfully.")
                    await self.message_queue.put({
                            "event": "application_removed",
                            "payload": data_dict
                        }
                    )
                    self.r.update_dict_value("endpoint_hash", model_id, "Removed")
                    self.r.remove_key("endpoint_hash", model_id)
                except ApiException as e:
                    if e.status == 404:
                        print(f"Custom Resource '{name}' not found. Skipping deletion.")
                    else:
                        print(f"Error deleting Custom Resource '{name}': {e}")
                        raise
            else:
                try:
                    timestamp = datetime.now()
                    info = {
                        'status': 'under_deployment',
                        'timestamp': str(timestamp)
                    }
                    self.r.update_dict_value("endpoint_hash", model_id, str(info))

                    # Transform and parse the description
                    file_content = transform_description(data_queue)
                    yaml_handler = yaml.safe_load(file_content)
                    cr_spec = yaml_handler

                    await self.message_queue.put(
                        {
                            "event": "application_submitted",
                            "payload": file_content
                        }
                    )
                    
                    logger.debug(f"Creating or updating Custom Resource: {name}")
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
                        logger.debug(f"Custom Resource '{name}' updated successfully.")
                    except ApiException as e:
                        logger.debug(f"Error processing Custom Resource: {e}")
                        if e.status == 404:
                            logger.debug(f"creating Custom Resource: {name} {group} {version} {namespace} {plural} {cr_spec}")
                            # Resource does not exist; create it
                            await custom_api.create_namespaced_custom_object(
                                group=group,
                                version=version,
                                namespace=namespace,
                                plural=plural,
                                body=cr_spec
                            )
                            logger.debug(f"Custom Resource '{name}' created successfully.")
                        else:
                            logger.error(f"Error processing Custom Resource: {e}")

                    # Add Check ML deployment behaviour
                    ml_check_behaviour = Check_ml_deployment_Behaviour(self.r, model_id, comp_name, custom_api)
                    self.agent.add_behaviour(ml_check_behaviour)

                except Exception as e:
                    logger.error(f"Error during deployment of '{name}': {e}")
                    self.r.update_dict_value("endpoint_hash", model_id, "Deployment_Failed")

            await asyncio.sleep(1)
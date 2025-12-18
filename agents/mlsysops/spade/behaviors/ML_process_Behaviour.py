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
from ruamel.yaml import YAML

from spade.behaviour import OneShotBehaviour
# Make sure to import the ML check behavior from its module.
from .Check_ml_deployment_Behaviour import Check_ml_deployment_Behaviour
from datetime import datetime

from mlstelemetry import MLSTelemetry
from ...logger_util import logger
from jinja2 import Template, PackageLoader, Environment, select_autoescape

import kubernetes_asyncio
from kubernetes_asyncio.client.api import CustomObjectsApi
from kubernetes_asyncio.client import ApiException
import traceback
mlsTelemetryClient = MLSTelemetry("continuum", "agent")

sleep_time = 1


from spade.behaviour import CyclicBehaviour

def transform_description(input_dict):
    # Extract the name and other fields under "MLSysOpsApplication"
    ml_sys_ops_data = input_dict.pop("MLSysOpsApp", {})
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

    return yaml_output, updated_dict

def create_svc_manifest(name_suffix=None,selector=""):
    """Create manifest for service-providing component using Jinja template.
       Returns:
           manifest (str): The rendered service manifest as a string.
       """

    loader = PackageLoader("mlsysops", "templates")
    env = Environment(
        loader=loader,
        autoescape=select_autoescape(enabled_extensions=("j2"))
    )
    template = env.get_template('ml-component-service.j2')
    name = f"ml-{name_suffix}"
    # Render the template with the context data
    manifest = template.render({
        'name': name,
        'type': "ClusterIP",
        'selector': selector,
        "ml_comp_port": "8000",
    })

    yaml = YAML(typ='safe',pure=True)
    manifest_dict = yaml.load(manifest)

    return manifest_dict

async def create_svc(name_suffix=None,svc_manifest=None,selector=None):
    """Create a Kubernetes service.

    Note: For testing it deletes the service if already exists.

    Args:
        svc_manifest (dict): The Service manifest.

    Returns:
        svc (obj): The instantiated V1Service object.
    """
    async with kubernetes_asyncio.client.ApiClient() as api_client:
        namespace = "mlsysops"
        core_api = kubernetes_asyncio.client.CoreV1Api(api_client)

        if svc_manifest is None:
            svc_manifest = create_svc_manifest(name_suffix,selector)
        resp = None
        try:
            logger.info('Trying to read service if already exists')
            resp = await core_api.read_namespaced_service(
                name=svc_manifest['metadata']['name'],
                namespace=namespace)
        except ApiException as exc:
            if exc.status != 404:
                logger.error('Unknown error reading service: %s', exc)
                return None
        if resp:
            try:
                logger.info('Trying to delete service if already exists')
                await core_api.delete_namespaced_service(
                    name=svc_manifest['metadata']['name'],
                    namespace=namespace)
            except ApiException as exc:
                logger.error('Failed to delete service: %s', exc)
        try:
            logger.info(f'Trying to create service {namespace}')
            logger.debug(svc_manifest)
            svc_obj = await core_api.create_namespaced_service(body=svc_manifest,
                                                         namespace=namespace)
            return svc_obj
        except ApiException as exc:
            logger.error('Failed to create service: %s', exc)
            return None

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
            logger.info(f" Karmada api config Loaded with external kubeconfig: {karmada_api_kubeconfig}")
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
            data_queue = json.loads(q_info)
            logger.debug(data_queue)
            if 'MLSysOpsApp' not in data_queue:
                model_id = list(data_queue.keys())[0]
            else:
                model_id = data_queue["MLSysOpsApp"]["components"][0]["metadata"]["uid"]
                # data_queue['MLSysOpsApp']['name'] = data_queue['MLSysOpsApp']['name'] + "-" + model_id
                data_queue['MLSysOpsApp']['name'] = model_id

                try:
                    comp_name = data_queue["MLSysOpsApp"]["components"][0]["metadata"]["name"]
                    cluster_id = data_queue["MLSysOpsApp"]["cluster_placement"]["cluster_id"][0]

                    self.r.update_dict_value("ml_location", model_id, cluster_id)
                except KeyError:
                    cluster_id = self.r.get_dict_value("ml_location", model_id)

            group = "mlsysops.eu"
            version = "v1"
            plural = "mlsysopsapps"
            namespace = "mlsysops"
            name = model_id
            queue_state = self.r.get_dict_value("endpoint_hash", model_id)
            logger.debug(f"Queue state: {queue_state}")
            if queue_state == "To_be_removed":
                try:
                    # Delete the existing custom resource
                    await custom_api.delete_namespaced_custom_object(
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=plural,
                        name=name
                    )
                    # await self.message_queue.put({
                    #         "event": "application_removed",
                    #         "payload": data_queue
                    #     }
                    # )
                    self.r.update_dict_value("endpoint_hash", model_id, "Removed")
                    self.r.remove_key("endpoint_hash", model_id)
                    logger.debug(f"Custom Resource '{name}' deleted successfully.")

                except ApiException as e:
                    if e.status == 404:
                        logger.debug(f"Custom Resource '{name}' not found. Skipping deletion.")
                    else:
                        logger.debug(f"Error deleting Custom Resource '{name}': {e}")
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
                    file_content, updated_dict = transform_description(data_queue)
                    yaml_handler = yaml.safe_load(file_content)
                    cr_spec = yaml_handler

                    # await self.message_queue.put(
                    #     {
                    #         "event": "application_submitted",
                    #         "payload": data_queue
                    #     }
                    # )

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
                            # Create ML Component Service
                            await create_svc(name_suffix=model_id,
                                             selector=f"{model_id}")

                        else:
                            logger.error(f"Error processing Custom Resource: {e}")

                    # Add Check ML deployment behaviour
                    ml_check_behaviour = Check_ml_deployment_Behaviour(self.r, model_id, comp_name, custom_api)
                    self.agent.add_behaviour(ml_check_behaviour)

                except Exception as e:
                    logger.error(f"Error during deployment of '{name}': {e}")
                    logger.error(traceback.format_exc())
                    self.r.update_dict_value("endpoint_hash", model_id, "Deployment_Failed")

            await asyncio.sleep(1)
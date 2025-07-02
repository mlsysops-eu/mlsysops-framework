#   Copyright (c) 2025. MLSysOps Consortium
#   #
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#   #
#       http://www.apache.org/licenses/LICENSE-2.0
#   #
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#  #
#  #

import asyncio
import copy
import os

from ruamel import yaml

from mlsysops.logger_util import logger
from mlsysops import MessageEvents

queues = {"inbound": None, "outbound": None}

import kubernetes_asyncio
from kubernetes_asyncio.client.api import CustomObjectsApi
from kubernetes_asyncio.client import ApiException
from ruamel.yaml import YAML


async def initialize(inbound_queue=None, outbound_queue=None):
    queues["inbound"] = inbound_queue
    queues["outbound"] = outbound_queue

    # Reverse the in- and out-, to make it more clear.


def create_cr(plan):

    cluster_value = plan["action"]["component"]
    app = plan.get("app")
    app_description = app[0]
    app_copy = copy.deepcopy(app_description)

    app_name = app_copy.pop("name", "")
    logger.debug(f"App name is  {app_name}")
    wrapped = {
        "apiVersion": "mlsysops.eu/v1",
        "kind": "MLSysOpsApp",
        "metadata": {"name": app_name},
    }

    wrapped.update(app_copy)

    if "cluster_placement" in wrapped:
        wrapped["cluster_placement"]["cluster_id"] = [cluster_value]
    else:
        wrapped["cluster_placement"] = {
            "cluster_id": [cluster_value],
            "instances": 1,
        }

    yaml_output = YAML(typ="unsafe", pure=True)
    filename = f"CR-{app_name}.yaml"
    with open(filename, "w") as f:
        # Pass the file‐handle into dump()
        yaml_output.dump(wrapped, f)
    return app_name


async def apply(plan):
    logger.debug(f"Applying Cluster Placement plan {plan}")

    app_id = create_cr(plan)

    logger.info(f"Applying CR in Karmada: {app_id}")

    karmada_api_kubeconfig = os.getenv("KARMADA_API_KUBECONFIG", "kubeconfigs/karmada-api.kubeconfig")

    try:
        await kubernetes_asyncio.config.load_kube_config(config_file=karmada_api_kubeconfig)
    except kubernetes_asyncio.config.ConfigException:
        logger.info("Running out-of-cluster configuration.")
        return

    # Initialize Kubernetes API client
    async with kubernetes_asyncio.client.ApiClient() as api_client:
        custom_api = CustomObjectsApi(api_client)

        group = "mlsysops.eu"
        version = "v1"
        plural = "mlsysopsapps"
        namespace = "mlsysops"
        name = app_id

        # Create or update the custom resource
        logger.info(f"Creating or updating Custom Resource: {name}")

        yaml = YAML(typ="safe")
        path = f"CR-{app_id}.yaml"
        with open(path, "r") as fh:
            cr_spec = yaml.load(fh)

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

async def delete_cr(name):
    logger.debug(f"deleting Cluster Placement plan {name}")

    karmada_api_kubeconfig = os.getenv("KARMADA_API_KUBECONFIG", "kubeconfigs/karmada-api.kubeconfig")

    try:
        await kubernetes_asyncio.config.load_kube_config(config_file=karmada_api_kubeconfig)
    except kubernetes_asyncio.config.ConfigException:
        logger.info("Running out-of-cluster configuration.")
        return

    # Initialize Kubernetes API client
    async with kubernetes_asyncio.client.ApiClient() as api_client:
        custom_api = CustomObjectsApi(api_client)

        group = "mlsysops.eu"
        version = "v1"
        plural = "mlsysopsapps"
        namespace = "mlsysops"

        try:
            current_resource = await custom_api.delete_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=name
            )
        except ApiException as e:
            logger.error(f"Error deleting Custom Resource: {e}")


async def send_message(msg):
    logger.debug(f"Sending message to spade {msg}")
    ## Delete namespaced object
    if msg['event'] == MessageEvents.APP_REMOVED.value:
        await delete_cr(msg['payload']["name"])

def get_state():
    pass


def get_options():
    pass

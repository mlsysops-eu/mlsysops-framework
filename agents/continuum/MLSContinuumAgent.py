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
import os
import time
import traceback
from glob import glob

import kubernetes.client.rest

from mlsysops.agent import MLSAgent
from mlsysops.events import MessageEvents
from mlsysops.logger_util import logger

from kubernetes_asyncio.client.rest import ApiException
import kubernetes_asyncio
from kubernetes_asyncio import config, client
from kubernetes import client, config

from jinja2 import Environment, FileSystemLoader  # Add Jinja2 import for template rendering
from ruamel.yaml import YAML  # YAML parser for handling PropagationPolicy definitions

import os
import traceback
from glob import glob
from jinja2 import Environment, FileSystemLoader
from kubernetes import client, config
from ruamel.yaml import YAML
from mlsysops.logger_util import logger

class MLSContinuumAgent(MLSAgent):

    def __init__(self):

        logger.debug("Starting MLSContinuumAgent process...")

        # Initialize base MLS agent class
        super().__init__()

        # Application
        self.active_components = {}  # Dictionary to track active application MLSComponent
        self.clusters = {}
        self.directory = "descriptions"
        # Kubeconfigs - the default communicates with the Karmada host cluster, and second is the Karmada API
        # need to have the karmada api as a file
        self.karmada_api_kubeconfig = os.getenv("KARMADA_API_KUBECONFIG", "/etc/mlsysops/kubeconfigs/karmada-api.kubeconfig")
        self.yaml_parser = YAML(typ='safe')

    async def run(self):
        """
        Main process of the MLSAgent.
        """
        await super().run()

        logger.info("Starting MLSAgent process...")
        self.clusters = await self.get_karmada_clusters()

        logger.info("Applying propagation policies...")
        await self.apply_propagation_policies()
        logger.info("Applying CRDs...")
        await self.ensure_crds()

        # Start the message queue listener task
        message_queue_task = asyncio.create_task(self.message_queue_listener())
        self.running_tasks.append(message_queue_task)

        try:
            results = await asyncio.gather(*self.running_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task raised an exception: {result}")
        except Exception as e:
            logger.error(f"Error in running tasks: {e}")

        logger.critical("MLSAgent stopped.")

    async def message_queue_listener(self):
        """
        Task to listen for messages from the message queue and act upon them.
        """
        logger.info("CONT_MLS_AGENT::::Starting Message Queue Listener...")
        while True:
            try:
                # Wait for a message from the queue
                message = await self.message_queue.get()
                logger.debug(f"MLS AGENT ::::: Received message: {message}")

                # Extract event type and application details from the message
                event = message.get("event")  # Expected event field
                raw = message.get("payload")  # Additional application-specific data
                data = raw["MLSysOpsApp"]

                # Act upon the event type
                if event == MessageEvents.APP_SUBMIT.value:
                    logger.debug(f"Sending to controller that app is submitted: {data}")
                    await self.application_controller.on_application_received(data)
                    await self.policy_controller.start_application_policies(data['name'])
                if event == MessageEvents.APP_REMOVED.value:
                    logger.debug(f"Sending to controller that app is removed: {data}")
                    await self.application_controller.on_application_terminated(data['name'])
                    await self.policy_controller.delete_application_policies(data['name'])

                    await self.state.active_mechanisms["clusterPlacement"]['module'].send_message({
                        "event": MessageEvents.APP_REMOVED.value,
                        "payload": {"name": data['name']},
                    })
                else:
                    logger(f"Unhandled event type: {event}")

            except Exception as e:
                logger.info(f"Error processing message: {e}")
                logger.exception(traceback.format_exc())

    async def apply_propagation_policies(self):
        """
        Dynamically generate and apply a PropagationPolicy using the active clusters from self.clusters.
        """
        try:
            # Extract cluster names where the cluster status is True (ready)
            cluster_names = [name for name, status in self.clusters.items() if status.lower() == 'true']

            logger.debug(f"Applying PropagationPolicy with cluster names: {cluster_names}")

            env = Environment(loader=FileSystemLoader(searchpath="./templates"))  # Load from "templates" dir

            # Apply Cluster-Wide PropagationPolicy
            try:
                name = "mlsysops-applicationcrd-propagation-policy"
                cluster_template = env.get_template("cluster-propagation-policy.yaml")
                rendered_cluster_policy = cluster_template.render(name=name,cluster_names=cluster_names)

                # Parse YAML to Python dictionary
                yaml = YAML(typ='safe')
                cluster_policy_body = yaml.load(rendered_cluster_policy)

                # Apply the Cluster-Wide PropagationPolicy
                await self._apply_policy(
                    policy_name=name,
                    policy_body=cluster_policy_body,
                    plural="clusterpropagationpolicies",
                    namespaced=False,
                )

            except Exception as e:
                logger.error(f"Error applying Cluster-Wide PropagationPolicy: {e}")

            # Apply Simple PropagationPolicy
            try:
                name = "mlsysops-propagate-policy"
                simple_template = env.get_template("application-cr-propagation-policy.yaml")
                rendered_simple_policy = simple_template.render(name=name,cluster_names=cluster_names)

                # Parse YAML to Python dictionary
                yaml = YAML(typ='safe')
                simple_policy_body = yaml.load(rendered_simple_policy)

                # Apply the Simple PropagationPolicy
                await self._apply_policy(
                    policy_name=name,
                    policy_body=simple_policy_body,
                    plural="propagationpolicies",
                    namespaced=True,
                    namespace="mlsysops"
                )

            except Exception as e:
                logger.error(f"Error applying Simple PropagationPolicy: {e}")

        except Exception as e:
            logger.error(f"Error applying PropagationPolicies: {e}")

    async def _apply_policy(self, policy_name: str, policy_body: dict, plural: str, namespaced: bool = False, namespace: str = None):
        """
        Apply or update a resource in Karmada.

        Handles both namespaced and cluster-scoped resources.

        :param policy_name: The name of the resource (used for identification).
        :param policy_body: The body of the resource as a Python dictionary.
        :param plural: The plural name of the resource (e.g., "propagationpolicies" or "clusterpropagationpolicies").
        :param namespaced: Whether the resource is namespaced (True) or cluster-scoped (False).
        :param namespace: The namespace to target for namespaced resources (required if namespaced=True).
        """
        try:
            # Load the Kubernetes configuration
            await kubernetes_asyncio.config.load_kube_config(config_file=self.karmada_api_kubeconfig, context='karmada-apiserver')

            async with kubernetes_asyncio.client.ApiClient() as api_client:
                custom_api = kubernetes_asyncio.client.CustomObjectsApi(api_client)

                # Define API group and version (specific to Karmada policies)
                group = "policy.karmada.io"
                version = "v1alpha1"

                logger.debug(
                    f"Applying resource '{policy_name}' with group: {group}, version: {version}, plural: {plural}, namespaced: {namespaced}"
                )

                if namespaced and not namespace:
                    raise ValueError("Namespace must be provided for namespaced resources.")

                try:
                    if namespaced:
                        # Fetch the current resource in the given namespace
                        current_resource = await custom_api.get_namespaced_custom_object(
                            group=group,
                            version=version,
                            namespace=namespace,
                            plural=plural,
                            name=policy_name
                        )
                    else:
                        # Fetch the current cluster-scoped resource
                        current_resource = await custom_api.get_cluster_custom_object(
                            group=group,
                            version=version,
                            plural=plural,
                            name=policy_name
                        )

                    # Add the required resourceVersion field to the policy body
                    resource_version = current_resource["metadata"]["resourceVersion"]
                    policy_body["metadata"]["resourceVersion"] = resource_version

                    logger.info(f"Resource '{policy_name}' exists. Updating it...")

                    # Perform an update using replace
                    if namespaced:
                        await custom_api.replace_namespaced_custom_object(
                            group=group,
                            version=version,
                            namespace=namespace,
                            plural=plural,
                            name=policy_name,
                            body=policy_body
                        )
                    else:
                        await custom_api.replace_cluster_custom_object(
                            group=group,
                            version=version,
                            plural=plural,
                            name=policy_name,
                            body=policy_body
                        )
                    logger.info(f"Resource '{policy_name}' updated successfully.")

                except kubernetes_asyncio.client.exceptions.ApiException as e:
                    if e.status == 404:
                        # If the resource doesn't exist, create a new one
                        logger.info(f"Resource '{policy_name}' not found. Creating a new one...")

                        # Create the new resource
                        if namespaced:
                            await custom_api.create_namespaced_custom_object(
                                group=group,
                                version=version,
                                namespace=namespace,
                                plural=plural,
                                body=policy_body
                            )
                        else:
                            await custom_api.create_cluster_custom_object(
                                group=group,
                                version=version,
                                plural=plural,
                                body=policy_body
                            )
                        logger.info(f"New resource '{policy_name}' created successfully.")
                else:
                    raise  # Re-raise any non-404 exceptions

        except Exception as e:
            logger.error(f"Error applying resource '{policy_name}': {e}")

    async def ensure_crds(self):
        """Ensure all MLSysOps CRDs are registered.

        Checks if the MLSysOps-related resource definitions are registered and
        registers any missing.
        """

        #: the REST API group name
        API_GROUP = 'mlsysops.eu'
        #: System file directory of CRDs
        _CRDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates/'))

        mlsysops_node_dict = {
            'singular': 'mlsysopsnode',
            'plural': 'mlsysopsnodes',
            'kind': 'MLSysOpsNode',
            'crd_name': f'mlsysopsnodes.{API_GROUP}',
            'crd_file': f'{_CRDS_DIR}/MLSysOpsNode.yaml',
            'version': 'v1'
        }

        mlsysops_app_dict = {
            'singular': 'mlsysopsapp',
            'plural': 'mlsysopsapps',
            'kind': 'MLSysOpsApp',
            'crd_name': f'mlsysopsapps.{API_GROUP}',
            'crd_file': f'{_CRDS_DIR}/MLSysOpsApplication.yaml',
            'version': 'v1'
        }

        mlsysops_cont_dict = {
            'singular': 'mlsysopscontinuum',
            'plural': 'mlsysopscontinuums',
            'kind': 'MLSysOpsContinuum',
            'crd_name': f'mlsysopscontinuums.{API_GROUP}',
            'crd_file': f'{_CRDS_DIR}/MLSysOpsContinuum.yaml',
            'version': 'v1'
        }

        mlsysops_cluster_dict = {
            'singular': 'mlsysopscluster',
            'plural': 'mlsysopsclusters',
            'kind': 'MLSysOpsCluster',
            'crd_name': f'mlsysopsclusters.{API_GROUP}',
            'crd_file': f'{_CRDS_DIR}/MLSysOpsCluster.yaml',
            'version': 'v1'
        }

        #: list: List with info regarding the supported custom resources
        CRDS_INFO_LIST = [mlsysops_node_dict, mlsysops_app_dict, mlsysops_cont_dict, mlsysops_cluster_dict]

        # connect to karmada api
        await kubernetes_asyncio.config.load_kube_config(config_file=self.karmada_api_kubeconfig)
        async with kubernetes_asyncio.client.ApiClient() as api_client:
            ext_api = kubernetes_asyncio.client.ApiextensionsV1Api(api_client)
            # Get the list of registered CRD names
            current_crds_response = await ext_api.list_custom_resource_definition()
            current_crds = current_crds_response.to_dict()['items']
            current_crds_names = [x['spec']['names']['singular'] for x in current_crds]

            for crd_info in CRDS_INFO_LIST:
                if crd_info['singular'] in current_crds_names:
                    logger.info('MLSysOps CRD: %s already exists', crd_info['kind'])
                else:
                    logger.info('Creating MLSysOps CRD: %s', crd_info['kind'])
                    try:
                        yaml = YAML(typ='safe')
                        with open(crd_info['crd_file'], 'r') as data:
                            body = yaml.load(data)
                    except IOError:
                        logger.error('Resource definition not in dir %s.',
                                     crd_info['crd_file'])
                    try:
                        await ext_api.create_custom_resource_definition(body)
                    except ApiException as exc:
                        logger.exception('%s update failed: %s', crd_info['kind'], exc)

    async def get_karmada_clusters(self):
        """
        Retrieve the clusters registered in Karmada, replicating 'kubectl get clusters'.

        :param kubeconfig_path: The path to the kubeconfig file.
        :return: A list of cluster names and their details.
        """
        try:
            # Load the kubeconfig file with the specified path
            await kubernetes_asyncio.config.load_kube_config(config_file=self.karmada_api_kubeconfig)

            # Create an API client for the Custom Resources API
            api_client = kubernetes_asyncio.client.CustomObjectsApi()

            # Query the 'clusters' custom resource in the 'clusters.karmada.io' API group
            group = "cluster.karmada.io"
            version = "v1alpha1"
            namespace = ""  # Clusters are cluster-scoped, no specific namespace
            plural = "clusters"

            response = await api_client.list_cluster_custom_object(
                group=group,
                version=version,
                plural=plural
            )

            # Process the response to extract cluster names and details
            clusters = []
            for item in response.get("items", []):
                clusters.append({
                    "name": item["metadata"]["name"],
                    "status": item.get("status", {}).get("conditions", "Unknown")
                })

            return_object = {}
            for cluster in clusters:
            # example
            # [{'name': 'uth-dev-cluster', 'status': [
            #     {'type': 'Ready', 'status': 'False', 'lastTransitionTime': '2025-04-07T10:24:31Z',
            #      'reason': 'ClusterNotReachable', 'message': 'cluster is not reachable'}]}, {'name': 'uth-prod-cluster',
            #                                                                                  'status': [
            #                                                                                      {'type': 'Ready',
            #                                                                                       'status': 'True',
            #  'lastTransitionTime': '2025-05-13T15:48:28Z',
            #  reason': 'ClusterReady',
            #  message': 'cluster is healthy and ready to accept workloads'}]}]
                return_object[cluster['name']] = cluster['status'][0]['status'] # true online, false offline
            return return_object

        except Exception as e:
            logger.error(f"Error retrieving clusters: {e}")
            return []
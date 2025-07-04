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
from datetime import datetime
from kubernetes import client, config

from kubernetes.client import ApiException
from spade.behaviour import OneShotBehaviour
from ...logger_util import logger

def get_pod_info(comp_name, model_id, api_client):
    """Query Karmada proxy API to find the pod with the given component name."""
    path = "/apis/search.karmada.io/v1alpha1/proxying/karmada/proxy/api/v1/namespaces/default/pods"
    try:
        response = api_client.call_api(
            resource_path=path, method="GET", auth_settings=["BearerToken"],
            response_type="json", _preload_content=False
        )
        pods = json.loads(response[0].data.decode("utf-8"))

        for pod in pods.get("items", []):
            if pod["metadata"]["name"].startswith(comp_name) and pod["status"]["phase"] == "Running" \
                    and model_id in pod["metadata"]["labels"].get("mlsysops.eu/app"):
                logger.debug(f"Found running pod: {pod['metadata']['name']} on host: {pod['spec']['nodeName']}")
                return pod["metadata"]["name"], pod["spec"]["nodeName"], pod['metadata']['labels']['mlsysops.eu/app']

    except ApiException as exc:
        logger.error(f"Failed to fetch pods: {exc}")
        return None, None, None
    return None, None, None


def get_k8s_nodes(api_client):
    """Query Karmada proxy API for the list of nodes."""
    path = "/apis/search.karmada.io/v1alpha1/proxying/karmada/proxy/api/v1/nodes"
    try:
        response = api_client.call_api(
            resource_path=path, method="GET", auth_settings=["BearerToken"], response_type="json", _preload_content=False
        )
        nodes = json.loads(response[0].data.decode("utf-8"))
        return nodes.get("items", [])
    except ApiException as exc:
        logger.error(f"Failed to fetch nodes: {exc}")
        return []

def get_node_ip(host, api_client):
    """Query from Karmada proxy API to get the IP address of the given node."""
    nodes = get_k8s_nodes(api_client)
    node_ip = None

    for node in nodes:
        if node["metadata"]["name"] == host:
            internal_ip = None
            external_ip = None

            for address in node["status"]["addresses"]:
                if address["type"] == "ExternalIP":
                    external_ip = address["address"]
                    logger.debug(f"Node: {host}, External IP: {external_ip}")
                elif address["type"] == "InternalIP":
                    internal_ip = address["address"]
                    logger.debug(f"Node: {host}, Internal IP: {internal_ip}")

            # Decide which IP to use
            node_ip = external_ip if external_ip else internal_ip
            break

    if not node_ip:
        logger.error(f"Failed to resolve IP for node: {host}")
    return node_ip


# def get_node_ip(host):
#     # Get a list of the nodes
#     nodes = get_k8s_nodes()
#     node_ip = None
#     for node in nodes:
#         node_name = node.metadata.name
#         if node.metadata.name == host:
#             internal_ip = None
#             external_ip = None
#             addresses = node.status.addresses
#             print('Addresses ' + addresses)
#             for address in addresses:
#                 if address.type == "ExternalIP":
#                     external_ip = address.address
#                     print(f"Node: {node_name}, External IP: {external_ip}")
#                 elif address.type == "InternalIP":
#                     internal_ip = address.address
#                     print(f"Node: {node_name}, Internal IP: {internal_ip}")
#             if external_ip == None:
#                 print('External IP not found for node that should be accessible externally.')
#                 if internal_ip == None:
#                     print('Internal IP not found for node that should be accessible externally.')
#                 else:
#                     node_ip = internal_ip
#             else:
#                 node_ip = external_ip
#             break
#     return node_ip



class Check_ml_deployment_Behaviour(OneShotBehaviour):

    def __init__(self, redis_manager, model_id, comp_name, core_api):
        super().__init__()
        self.r = redis_manager
        self.model_id = model_id
        self.comp_name = comp_name
        self.core_api = core_api

    async def run(self):
        """Continuously process tasks from the Redis queue."""
        logger.debug("Checking deployment for Application ...")

        # Load Karmada kubeconfig and create Kubernetes API client
        karmada_api_kubeconfig = os.getenv("KARMADA_API_KUBECONFIG", "kubeconfigs/karmada-api.kubeconfig")
        try:
            config.load_kube_config(config_file=karmada_api_kubeconfig)
            api_client = client.ApiClient()
        except Exception as e:
            logger.error(f"Failed to load Karmada kubeconfig: {e}")
            return

        while True:
            pod_name, host, app_id = get_pod_info(self.comp_name, self.model_id, api_client)

            if not pod_name:
                logger.debug(f"Failed to find running pod for comp_name: {self.comp_name}, retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                logger.debug(f"Found pod: {pod_name} running on host: {host}")
                break

        svc_path = f"/apis/search.karmada.io/v1alpha1/proxying/karmada/proxy/api/v1/namespaces/default/services/{self.comp_name}"
        logger.debug(f"Fetching service details from Karmada proxy API: {svc_path}")
        try:
            response = api_client.call_api(
                resource_path=svc_path, method="GET", auth_settings=["BearerToken"], response_type="json", _preload_content=False
            )
            svc_obj = json.loads(response[0].data.decode("utf-8"))
        except ApiException as exc:
            logger.error(f"Failed to fetch service: {exc}")
            return

        if not svc_obj:
            logger.error(f"Service not found for {self.comp_name}")
            return

        # Retrieve the assigned ClusterIP and port
        local_endpoint = svc_obj["spec"]["clusterIP"] + ":" + str(svc_obj["spec"]["ports"][0]["port"])
        global_endpoint_port = str(svc_obj["spec"]["ports"][0].get("nodePort", ""))

        # Prepare and store deployment details
        if self.model_id is not None:
            timestamp = datetime.now()
            info = {
                "status": "deployed",
                "timestamp": str(timestamp),
                "local_endpoint": local_endpoint,
            }

            # Get node IP and include global endpoint details if available
            node_ip = get_node_ip(host, api_client)
            if global_endpoint_port and node_ip:
                info["global_endpoint"] = f"{node_ip}:{global_endpoint_port}"

            logger.debug(f"Pushing endpoint details to Redis: {info}")
            self.r.update_dict_value("endpoint_hash", self.model_id, str(info))

        await asyncio.sleep(2)

        # while True:
        #     pod_name = None
        #     # Waits until it reads a pod with the given name
        #     pod_name, host = get_pod_name(self.comp_name)
        #     # Retrieve svc endpoint info
        #     if pod_name is None:
        #         logger.debug('Failed to get status of comp with name ' + str(self.comp_name))
        #         await asyncio.sleep(5)
        #     else:
        #         break
        #
        # svc_obj = None
        # try:
        #     svc_obj = self.core_api.read_namespaced_service(
        #         name=self.comp_name,
        #         namespace=config.NAMESPACE)
        # except ApiException as exc:
        #     if exc.status != 404:
        #         print('Unknown error reading service: ' + exc)n
        #         return None
        #
        # # Retrieve svc endpoint info
        # if svc_obj is None:
        #     print('Failed to read svc with name ' + self.comp_name)
        #     # Add handling
        #
        # # Retrieve the assigned VIP:port
        # local_endpoint = svc_obj.spec.cluster_ip + ':' + str(svc_obj.spec.ports[0].port)
        # if svc_obj.spec.ports[0].node_port:
        #     global_endpoint_port = str(svc_obj.spec.ports[0].node_port)
        # else:
        #     global_endpoint_port = None
        #
        # if self.model_id != None:
        #     timestamp = datetime.now()
        #     info = {
        #         'status': 'deployed',
        #         'timestamp': str(timestamp),
        #         'local_endpoint': local_endpoint
        #     }
        #
        #     node_ip = get_node_ip(host)
        #     if global_endpoint_port and node_ip:
        #         info['global_endpoint'] = node_ip + ':' + global_endpoint_port
        #
        #     print('Going to push to redis_conf endpoint_queue the value ' + str(info))
        #     # NOTE: PLACEHOLDER FOR REDIS - YOU CAN CHANGE THIS WITH ANOTHER TYPE OF COMMUNICATION
        #     self.r.update_dict_value('endpoint_hash', self.model_id, str(info))
        #
        # await asyncio.sleep(2)
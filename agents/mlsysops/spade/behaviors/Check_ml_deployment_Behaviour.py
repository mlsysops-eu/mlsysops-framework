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
from datetime import datetime
from kubernetes import client, config

from kubernetes.client import ApiException
from spade.behaviour import OneShotBehaviour

def get_pod_name(comp_name):
    # Get list of the pods
    # Check which one starts with the comp_name and return it
    api = client.CoreV1Api()
    try:
        pods = api.list_namespaced_pod(namespace='default')
    except ApiException as exc:
        print('Failed to delete Pod: ' + exc)
        return None, None
    pod_list = pods.items
    for pod in pod_list:
        if pod.metadata.name.startswith(str(comp_name)):
            if pod.status.phase == 'Running':
                pod_name = "podname"
                # Return the pod name and the host.
                return pod_name, pod.spec.node_name
            else:
                return None, None
    return None, None

def get_k8s_nodes():
    """Get the list of k8s node objects.

    Returns:
        list: The nodes dictionaries.
    """
    # NOTE: USE THE CORRECT KUBECONFIG FILE HERE
    config.load_kube_config()
    api_instance = client.CoreV1Api()
    try:
        node_list = api_instance.list_node()
    except ApiException as exc:
        print('List node failed: ' + exc)
        return []
    return node_list.items

def get_node_ip(host):
    # Get a list of the nodes
    nodes = get_k8s_nodes()
    node_ip = None
    for node in nodes:
        node_name = node.metadata.name
        if node.metadata.name == host:
            internal_ip = None
            external_ip = None
            addresses = node.status.addresses
            print('Addresses ' + addresses)
            for address in addresses:
                if address.type == "ExternalIP":
                    external_ip = address.address
                    print(f"Node: {node_name}, External IP: {external_ip}")
                elif address.type == "InternalIP":
                    internal_ip = address.address
                    print(f"Node: {node_name}, Internal IP: {internal_ip}")
            if external_ip == None:
                print('External IP not found for node that should be accessible externally.')
                if internal_ip == None:
                    print('Internal IP not found for node that should be accessible externally.')
                else:
                    node_ip = internal_ip
            else:
                node_ip = external_ip
            break
    return node_ip



class Check_ml_deployment_Behaviour(OneShotBehaviour):

    def __init__(self, redis_manager, model_id, comp_name, core_api):
        super().__init__()
        self.r = redis_manager
        self.model_id = model_id
        self.comp_name = comp_name
        self.core_api = core_api

    async def run(self):
        """Continuously process tasks from the Redis queue."""
        print("Checking deployment for Application ...")

        while True:
            pod_name = None
            # Waits until it reads a pod with the given name
            pod_name, host = get_pod_name(self.comp_name)
            # Retrieve svc endpoint info
            if pod_name is None:
                print('Failed to get status of comp with name ' + str(self.comp_name))
                await asyncio.sleep(5)
            else:
                break

        svc_obj = None
        try:
            svc_obj = self.core_api.read_namespaced_service(
                name=self.comp_name,
                namespace='default')
        except ApiException as exc:
            if exc.status != 404:
                print('Unknown error reading service: ' + exc)
                return None

        # Retrieve svc endpoint info
        if svc_obj is None:
            print('Failed to read svc with name ' + self.comp_name)
            # Add handling

        # Retrieve the assigned VIP:port
        local_endpoint = svc_obj.spec.cluster_ip + ':' + str(svc_obj.spec.ports[0].port)
        if svc_obj.spec.ports[0].node_port:
            global_endpoint_port = str(svc_obj.spec.ports[0].node_port)
        else:
            global_endpoint_port = None

        if self.model_id != None:
            timestamp = datetime.now()
            info = {
                'status': 'deployed',
                'timestamp': str(timestamp),
                'local_endpoint': local_endpoint
            }

            node_ip = get_node_ip(host)
            if global_endpoint_port and node_ip:
                info['global_endpoint'] = node_ip + ':' + global_endpoint_port

            print('Going to push to redis_conf endpoint_queue the value ' + str(info))
            # NOTE: PLACEHOLDER FOR REDIS - YOU CAN CHANGE THIS WITH ANOTHER TYPE OF COMMUNICATION
            self.r.update_dict_value('endpoint_hash', self.model_id, str(info))

        await asyncio.sleep(2)
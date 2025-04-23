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
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from spade.behaviour import OneShotBehaviour
# Make sure to import the ML check behavior from its module.
from .Check_ml_deployment_Behaviour import Check_ml_deployment_Behaviour

command = "kubectl karmada --kubeconfig $HOME/.kube/karmada-apiserver.config apply -f ml-app.yaml"

from datetime import datetime
import subprocess

from mlstelemetry import MLSTelemetry

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

def create_yaml_file(yaml_string, output_file):
    # Write the YAML string to a file
    with open(output_file, 'w') as file:
        file.write(yaml_string)

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
        if pod.metadata.name.startswith(comp_name):
            if pod.status.phase == 'Running':
                pod_name = "podname"
                # Return the pod name and the host.
                return pod_name, pod.spec.node_name
            else:
                return None, None
    return None, None


class ML_process_Behaviour(CyclicBehaviour):
    """
          A behavior that processes tasks from a Redis queue in a cyclic manner.
    """

    def __init__(self, redis_manager):
        super().__init__()
        self.r = redis_manager


    async def run(self):
        """Continuously process tasks from the Redis queue."""
        print("MLs Agent is processing for ML Deployments...")

        if self.r.is_empty(self.r.ml_q):
            print("queue is empty waiting for next iteration")
            await asyncio.sleep(10)
        else:

            q_info = self.r.pop(self.r.ml_q)
            q_info = q_info.replace("'", '"')
            print(q_info)
            data_queue = json.loads(q_info)
            model_id = data_queue["MLSysOpsApplication"]["mlsysops-id"]

            try:
                comp_name = data_queue["MLSysOpsApplication"]["components"][0]["Component"]["name"]
                cluster_id = data_queue["MLSysOpsApplication"]["clusterPlacement"]["clusterID"][0]

                self.r.update_dict_value("ml_location", model_id, cluster_id)

            except:

                cluster_id = self.r.get_dict_value("ml_location"
                                                   ,model_id)  ## This is harcoded for testing think how to get the cluster info from deletion.
                print("CLUSTER ID  " +str(cluster_id))
            # Define kubeconfig path based on cluster_idf""

            kubeconfig_path = f"./kubeconfigs/{cluster_id}.kubeconfig"
            kubeconfig_path = "./kubeconfigs/UTH-AUG1.kubeconfig"  # Hard-coded for testing

            # Debug: print current working directory and absolute path
            #print("DEBUG: Current working directory:", os.getcwd())
            abs_path = os.path.abspath(kubeconfig_path)
            #print("DEBUG: Absolute kubeconfig path:", abs_path)

            try:
                with open(kubeconfig_path, 'r') as kube_file:
                    kubeconfig_content = kube_file.read()
                    #print("DEBUG: Contents of the kubeconfig file:")
                    #print(kubeconfig_content)
            except Exception as e:
                print(f"DEBUG: Failed to read kubeconfig file: {e}")

            config.load_kube_config(config_file=kubeconfig_path)
            core_api = client.CoreV1Api()

            if self.r.get_dict_value("endpoint_hash", model_id) == "To_be_removed":

                output_file = f"./ml-app-{model_id}.yaml"
                apply_kubectl(output_file, "delete")

                # logic to check if the pod is removed ..

                self.r.update_dict_value("endpoint_hash", model_id, "Removed")

                time.sleep(5)
                self.r.remove_key("endpoint_hash", model_id)

                print("REMOVED")

            else:

                timestamp = datetime.now()
                info = {
                    'status': 'under_deployment',
                    'timestamp': str(timestamp)
                }
                self.r.update_dict_value("endpoint_hash", model_id, str(info))
                file = transform_description(data_queue)
                output_file = f"ml-app-{model_id}.yaml"
                create_yaml_file(file, output_file)
                apply_kubectl(output_file)

                ml_check_behaviour = Check_ml_deployment_Behaviour(self.r, model_id, comp_name, core_api)

                self.agent.add_behaviour(ml_check_behaviour)

            await asyncio.sleep(10)
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

import string
import threading
import asyncio
import yaml
import random
import string
import kubernetes
import time
import pprint
import re
from kubernetes import client , config , watch
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from mlsysops.logger_util import logger
from kubernetes.client.rest import ApiException

initial_list = None
node_list_dict = None
node_counter = 0
configmap_list = None
namespace = 'mls-telemetry'
base_pod_name = 'opentelemetry-collector'
base_configmap_name = 'otel-collector-configmap'
# node_lock = []
task_list = None

class STATUS(Enum): # i use it to check if a node has an otel collector pod deployed and if not we should deploy it
    NOT_DEPLOYED = 0
    DEPLOYED = 1

def set_node_dict(v1: client.CoreV1Api) -> None:
    global node_list_dict # List of dictionaries
    global task_list
    """
     [dict1 , dict2, dict3]


     dict1 = {key:value} 
     key <- node_name <- [metadata][name]
     value <-  [pod_name , configmap_name ,enum STATUS, [metadata][labels] ] 

    """
    global node_counter
    global initial_list
    node_counter = 0
    try:
        node_list_dict = []
        initial_list = []
        http_response = v1.list_node() # http GET  , returns a V1NodeList object
        # Note, the responce is not an ordinary list , it contains V1Node objects

        item_list = http_response.items
        for item in item_list: # item represents a node dictionary , item : V1Node

            initial_list.append(item) # append V1Nodes , i use it later
            key = item.metadata.name # Get the key
            assigned_pod_name = pod_name + str(node_counter)
            label_value = item.metadata.labels # Get the labels

            config_name = configmap_name + str(node_counter)



            val = [assigned_pod_name , config_name , STATUS.NOT_DEPLOYED , label_value]
            node = {key : val}
            node_list_dict.append(node)
            node_counter += 1
        task_list = [None] * node_counter
    except client.exceptions.ApiException as e:
        if e.status == 404:
            print("Nodes not found (404).")
        elif e.status == 401:
            print("Unauthorized (401). Check your credentials.")
        else:
            print(f"An error occurred: {e}")
    except Exception as ex:
        print(f"Unexpected error: {ex}")
    return None


async def create_pod(v1: client.CoreV1Api, pod_name: str, node_name: str, configmap_name: str) -> None:
    # Define the pod spec
    pod_spec = client.V1Pod(
        metadata=client.V1ObjectMeta(
            name=pod_name,
            labels={"mls-telemetry/app": "otel-collector"
                    }),
        spec=client.V1PodSpec(
            containers=[
                client.V1Container(
                    name="otel-collector",
                    image="otel/opentelemetry-collector-contrib:0.113.0",
                    args=["--config=/etc/otel-collector-config/otel-collector-config.yaml"],
                    volume_mounts=[
                        client.V1VolumeMount(
                            name="otel-config-volume",
                            mount_path="/etc/otel-collector-config",
                            read_only=True
                        )
                    ],
                    env=[
                        client.V1EnvVar(
                            name="NODE_HOSTNAME",
                            value_from=client.V1EnvVarSource(
                                field_ref=client.V1ObjectFieldSelector(
                                    api_version="v1",
                                    field_path="spec.nodeName"
                                )
                            )
                        ),
                        client.V1EnvVar(
                            name="NODE_IP",
                            value_from=client.V1EnvVarSource(
                                field_ref=client.V1ObjectFieldSelector(
                                    api_version="v1",
                                    field_path="status.hostIP"
                                )
                            )
                        )
                    ]
                )
            ],
            volumes=[
                client.V1Volume(
                    name="otel-config-volume",
                    config_map=client.V1ConfigMapVolumeSource(name=configmap_name)
                )
            ],
            restart_policy="OnFailure",
            node_selector={"kubernetes.io/hostname": node_name}
        ),
    )

    try:
        http_response = v1.create_namespaced_pod(namespace=namespace, body=pod_spec)  # HTTP POST
        print(f"Pod {pod_name} created successfully on node {node_name} in namespace {namespace}.")
    except client.exceptions.ApiException as ex:
        if ex.status == 404:
            print(f"Status 404: Pod creation failed for pod {pod_name} in namespace {namespace}.")
        elif ex.status == 400:
            print(f"Bad request: Failed to create pod {pod_name} in namespace {namespace}.")
        else:
            print(f"Error creating Pod: {ex.reason} (code: {ex.status})")
    except Exception as e:
        print(str(e))
    return None

def delete_pod(v1:client.CoreV1Api , pod_name:str) -> None:

    try:
        http_response = v1.delete_namespaced_pod(name = pod_name, namespace= namespace,body = client.V1DeleteOptions(grace_period_seconds = 0))
        print(f'Pod with name {pod_name} from {namespace} namespace has been deleted')

    except client.exceptions.ApiException as e:
        if e.status == 404:
            print(f'Pod {pod_name} did not deleted. Error 404')
        else:
            print(e)
    return None


async def create_configmap(v1: client.CoreV1Api, configmap_name: str, otel_specs :str , verbose=False) -> client.V1ConfigMap:
    loop = asyncio.get_running_loop()  # Get the current event loop

    try:
        configmap = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=configmap_name),
            data={"otel-collector-config.yaml": otel_specs}
        )

        # Run the synchronous API call in a separate thread
        with ThreadPoolExecutor() as executor:
            created_configmap = await loop.run_in_executor(
                executor, v1.create_namespaced_config_map, namespace, configmap
            )

        if verbose:
            print(f"ConfigMap '{configmap_name}' created in namespace '{namespace}'.")
        return created_configmap

    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"ConfigMap '{configmap_name}' already exists in namespace '{namespace}'.")
        elif e.status == 400:
            print(f"Bad request in creating ConfigMap '{configmap_name}' in namespace '{namespace}'.")
        else:
            print(f"Error creating ConfigMap: {e.reason}")
        return None


    except client.exceptions.ApiException as e:
        if e.status == 409:  # ConfigMap already exists
            print(f"ConfigMap '{configmap_name}' already exists in namespace '{namespace}'.")
        elif e.status == 400:
            print(f'Bad request in creating {configmap_name} in {namespace} namespace ')
        else:
            print(f"Error creating ConfigMap: {e}")
        return None


def remove_configmap(v1: client.CoreV1Api, configmap_name: str) -> None:
    try:
        http_response = v1.delete_namespaced_config_map( name=configmap_name, namespace=namespace)

    except client.exceptions.ApiException as ex:
        logger.error(f"Error removing ConfigMap due to API '{configmap_name}': {ex.reason}")
    except Exception as ex:
        logger.error(f"Error removing ConfigMap '{configmap_name}': {ex}")

def remove_service() -> None:
    """
    Removes a specified Kubernetes service from a namespace.

    Args:
        v1 (client.CoreV1Api): An instance of the Kubernetes CoreV1Api client.
        service_name (str): The name of the service to delete.
        namespace (str): The namespace from which to delete the service.

    """
    config.load_kube_config()
    v1 = client.CoreV1Api()
    service_name = "otel-collector-svc"
    try:
        # Attempt to delete the service
        http_response = v1.delete_namespaced_service(name=service_name, namespace=namespace)
        logger.info(f"Service '{service_name}' deleted successfully from namespace '{namespace}'.")

    except client.exceptions.ApiException as ex:
        logger.error(f"Error removing Service '{service_name}' due to API error: {ex.reason}")
    except Exception as ex:
        logger.error(f"Error removing Service '{service_name}': {ex}")


async def read_configmap(v1: client.CoreV1Api , configmap_name: str) -> client.V1ConfigMap : # Return the configmap object not the dict
    try:
        configmap_obj =  v1.read_namespaced_config_map( name=configmap_name, namespace=namespace)
        return(configmap_obj)
    except Exception as ex:
        print(ex)
        return None

# def monitor_nodes(v1:client.CoreV1Api) -> None: # Always check for new nodes if added or deleted
#     w = watch.Watch()
#     try:

#         for event in w.stream(v1.list_node):
#             event_type = event["type"]
#             node_name = event["object"].metadata.name
#             print(f"Node Event: {event_type} - Node Name: {node_name}")

#     except Exception as ex:
#         print(ex)
#     finally:
#         w.stop()
#     return None

# def add_new_nodes(v1: client.CoreV1Api) -> None:
#     global node_list_dict
#     global initial_list
#     global node_counter
#     try:
#         http_response = v1.list_node()
#         new_item_list = http_response.items # New V1NodesList
#         for node in new_item_list :
#             if node.metadata.name not in {n.metadata.name for n in initial_list}: : # found a V1Node object that is not in the orginal list
#                 node_counter += 1
#                 key = node.metadata.name
#                 assigned_pod_name = pod_name + str(node_counter)
#                 config_name = configmap_name + str(node_counter)
#                 label_value = node.metadata.labels
#                 val = [assigned_pod_name , config_name , label_value]
#                 new_node = {key : val}
#                 node_list_dict.append(new_node) # Add the new node to our list of dictionaries
#                 initial_list.append(node)
#     except Exception as ex:
#         print(ex)
#     return None

# def monitor_pods(v1:client.CoreV1Api) -> None:
#     w = watch.Watch()
#     try:

#         for event in w.stream(v1.list_namespaced_pod, namespace="default"):
#             event_type = event["type"]
#             pod_name = event["object"].metadata.name
#             print(f"Pod Event: {event_type} - Node Name: {pod_name}")

#     except Exception as ex:
#         print(ex)
#     finally:
#         w.stop()
#     return None


async def redeploy_configmap(v1:client.CoreV1Api, otel_specs: str,configmap: client.V1ConfigMap) -> None:
    try :
        """ Configmap is a V1ConfigMap obj , we want to change the .data field with the new otel specs 
            We cannot access the configmap.data[key] like a list , because the .keys method returns a dictionary with keys and not a list
            we also could use the key name (see above) but i want to add more abstraction 
        """
        keys = configmap.data.keys()
        for key in keys:
            configmap.data[key] = otel_specs

        configmap_name = configmap.metadata.name # str

        http_response = v1.replace_namespaced_config_map(name = configmap_name, namespace = namespace,body = configmap) # http PUT
        # The body argument is a V1ConfigMap obj


    except client.exceptions.ApiException as ex:
        print(f'Could not redeploy configmap :{configmap_name} in namespace:{namespace} , reason: {ex.reason}')
    except Exception as e:
        print(e)
    return None


async def task_monitor(v1: client.CoreV1Api , node_list : list,otel:string) -> None:
    global task_list
    i = 0
    print('Task monitoring starts ...')
    while True :
        if task_is_active(task_list[i]) :
            await asyncio.sleep(1)
        else:
            task_list[i] = asyncio.create_task(restart_telemetry_pod(v1,node_list[i],i,otel,update_method = update_method))
        i = (i + 1) % node_counter
        await asyncio.sleep(60) # 3.2 minutes , so the i th pod will be restarted after 10 minutes
    return None
# Gather , check : is_running ,

async def create_otel_pod(node_name: str , otel_yaml:string) -> bool :
    """
        Creates an OpenTelemetry (OTEL) pod and its associated ConfigMap on the provided node.

        This asynchronous function is responsible for setting up the necessary ConfigMap and pod
        to enable OpenTelemetry functionality for a specific node in a Kubernetes cluster.

        Args:
            v1 (client.CoreV1Api): The Kubernetes CoreV1Api client to interact with the API.
            node_name (str): The name of the node on which the OTEL pod will be created.
            otel_yaml (str): The YAML configuration for the OTEL client.

        Returns:
            bool: True if the operation is successful, False otherwise.

        Raises:
            Exception: If an error occurs during the creation of ConfigMap or pod, the exception
                       is caught, logged, and the function returns False.
    """
    config.load_kube_config()
    v1 = client.CoreV1Api()

    logger.debug(f'OTEL Pod with name:{node_name} is been created')
    final_config_name = f"{base_configmap_name}-{node_name}"
    final_pod_name = f"{base_pod_name}-{node_name}"
    try:
        await create_configmap(v1, final_config_name, otel_yaml)
        await create_pod(v1, final_pod_name, node_name, final_config_name)
    except Exception as e:
        logger.error(f'Error creating pod for node {node_name} : {e}')
        return None,None

    return final_pod_name , final_config_name

def delete_otel_pod(node_name: str) -> bool:
    """
    Delete an OpenTelemetry pod and its associated ConfigMap on a specified node.

    The function removes the pod and its corresponding ConfigMap for a node specified
    by the name. If an error occurs during the deletion process, the function logs
    the error and returns False, indicating the failure of the operation.

    Parameters:
        v1 (client.CoreV1Api): An instance of the CoreV1Api class, used for
            making calls to the Kubernetes API.
        node_name (str): The name of the node where the OpenTelemetry pod exists.
        otel_yaml (string): A YAML configuration file for the OpenTelemetry pod.

    Returns:
        bool: True if the pod and ConfigMap are successfully deleted, otherwise False.
    """
    config.load_kube_config()
    v1 = client.CoreV1Api()

    final_config_name = f"{base_configmap_name}-{node_name}"
    final_pod_name = f"{base_pod_name}-{node_name}"
    try:
        delete_pod(v1, final_pod_name)
        remove_configmap(v1, final_config_name)
    except Exception as e:
        logger.error(f'Error creating pod for node {node_name} : {e}')
        return False

    return True


async def restart_telemetry_pod(v1: client.CoreV1Api , node : dict , node_id : int  , otel:string ,update_method = None) -> None :
    global node_list_dict



    node_values_list = list(node.values())[0]
    config_name = node_values_list[1]
    pod_name    = node_values_list[0]
    node_status = node_values_list[2]


    node_name = next(iter(node)) # Get the nodes name )

    if node_status == STATUS.NOT_DEPLOYED:
        print(f'Node with id:{node_id} is been created')
        await create_configmap(v1,config_name,otel)
        await  create_pod(v1,pod_name,node_name,config_name)
        node_list_dict[node_id][node_name][2] = STATUS.DEPLOYED

        await asyncio.sleep(5)
        print(f'Node with id:{node_id} done')
        return None

    else:
        print(f'Restart Node with id:{node_id} ')
        configmap = await read_configmap(v1,config_name) # Get V1ConfigMap object
        data = configmap.data # dict(str:str)
        otel_specs = "\n".join(data.values()) # opentelemetry configuration
        otel_specs = update_method(otel_specs)

            # Impelemnt an update method and redeploy configmap
        await redeploy_configmap(v1,otel_specs,configmap)
        await delete_pod(v1,pod_name)
        await create_pod(v1,pod_name,node_name,config_name)
        # await asyncio.sleep(1)
        print(f'Node with id{node_id} has finished restarting')

    return None


def create_svc_manifest():
    """Create manifest for service-providing component.
    Returns:
        manifest (dict): The respective service manifest.
    """

    manifest = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'name': "otel-collector-svc"
        },
        'spec': {
            'type': "ClusterIP",
            'ports': [
                {
                    'name': "otlp-grpc",
                    'port': 43170,
                    'protocol': "TCP",
                    'targetPort': 43170,
                },
                {
                    'name': "otlp-http",
                    'port': 43180,
                    'protocol': "TCP",
                    'targetPort': 43180,
                },{
                    'name': 'prom',
                    'port': 9999,
                    'protocol': "TCP",
                    'targetPort': 9999,
                },
            ],
            'selector': {
                'mls-telemetry/app': "otel-collector",
            }
        }
    }
    return manifest


async def create_svc(svc_manifest=None):
    """Create a Kubernetes service.

    Note: For testing it deletes the service if already exists.

    Args:
        svc_manifest (dict): The Service manifest.

    Returns:
        svc (obj): The instantiated V1Service object.
    """
    config.load_kube_config()
    core_api = client.CoreV1Api()
    if svc_manifest is None:
        svc_manifest = create_svc_manifest()
    resp = None
    try:
        logger.info('Trying to read service if already exists')
        resp = core_api.read_namespaced_service(
            name=svc_manifest['metadata']['name'],
            namespace='mls-telemetry')
        #print(resp)
    except ApiException as exc:
        if exc.status != 404:
            logger.error('Unknown error reading service: %s', exc)
            return None
    if resp:
        try:
            logger.info('Trying to delete service if already exists')
            resp = core_api.delete_namespaced_service(
                name=svc_manifest['metadata']['name'],
                namespace='mls-telemetry')
            #print(resp)
        except ApiException as exc:
            logger.error('Failed to delete service: %s', exc)
    try:
        svc_obj = core_api.create_namespaced_service(body=svc_manifest,
                                                     namespace='mls-telemetry')
        #print(svc_obj)
        return svc_obj
    except ApiException as exc:
        logger.error('Failed to create service: %s', exc)
        return None
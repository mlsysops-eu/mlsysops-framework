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
import os
import asyncio
import string
import traceback

from kubernetes import client , config , watch
from enum import Enum

from ruamel.yaml import YAML

from mlsysops.logger_util import logger
from kubernetes.client.rest import ApiException
from jinja2 import Environment, FileSystemLoader, PackageLoader, select_autoescape

initial_list = None
node_list_dict = None
node_counter = 0
configmap_list = None
namespace = 'mls-telemetry'
base_pod_name = 'opentelemetry-collector'
base_configmap_name = 'otel-collector-configmap'
# node_lock = []
task_list = None

client_handler = None

class STATUS(Enum): # i use it to check if a node has an otel collector pod deployed and if not we should deploy it
    NOT_DEPLOYED = 0
    DEPLOYED = 1

def get_api_handler():
    global client_handler
    if client_handler is None:
        if 'KUBERNETES_PORT' in os.environ:
            config.load_incluster_config()
        else:
            config.load_kube_config()
        client_handler = client.CoreV1Api()
    return client_handler


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


def create_pod_spec(pod_name: str, node_name: str, configmap_name: str) -> str:
    """Create a pod manifest using a Jinja template.

    Args:
        pod_name (str): Name of the pod.
        node_name (str): Name of the node.
        configmap_name (str): Name of the ConfigMap.

    Returns:
        str: The rendered pod manifest as a string.
    """
    loader = PackageLoader("mlsysops", "templates")
    env = Environment(
        loader=loader,
        autoescape=select_autoescape(enabled_extensions=("j2"))
    )
    template = env.get_template('otel-collector-pod-definition.yml.j2')

    # Render the template
    manifest = template.render({
        'pod_name': pod_name,
        'node_name': node_name,
        'configmap_name': configmap_name,
        "otlp_grpc_port": int(os.getenv("MLS_OTEL_GRPC_PORT", "43170")),
        "otlp_http_port": int(os.getenv("MLS_OTEL_HTTP_PORT", "43180")),
        "otlp_prometheus_port": int(os.getenv("MLS_OTEL_PROM_PORT", "9999"))
    })

    yaml = YAML(typ='safe', pure=True)
    manifest_dict = yaml.load(manifest)

    return manifest_dict


async def create_pod(v1: client.CoreV1Api, pod_name: str, node_name: str, configmap_name: str) -> None:
    # Define the pod spec
    pod_spec = create_pod_spec(pod_name,node_name, configmap_name)
    logger.debug(f'Pod spec is {pod_spec}')
    try:
        http_response = v1.create_namespaced_pod(namespace=namespace, body=pod_spec)  # HTTP POST
        logger.info(f"Pod {pod_name} created successfully on node {node_name} in namespace {namespace}.")
    except client.exceptions.ApiException as ex:
        if ex.status == 404:
            logger.error(f"Status 404: Pod creation failed for pod {pod_name} in namespace {namespace}.")
        elif ex.status == 400:
            logger.error(f"Bad request: Failed to create pod {pod_name} in namespace {namespace}.")
            logger.error(traceback.format_exc())
        else:
            logger.error(f"Error creating Pod: {ex.reason} (code: {ex.status})")
    except Exception as e:
        logger.error(str(e))
    return None


def create_node_exporter_pod_spec(pod_name: str, node_name: str, flags: str, port: int) -> dict:
    """Create a pod manifest using a Jinja template.

    Args:
        pod_name (str): Name of the pod.
        node_name (str): Name of the node.
        configmap_name (str): Name of the ConfigMap.

    Returns:
        str: The rendered pod manifest as a string.
    """
    global namespace
    loader = PackageLoader("mlsysops", "templates")
    env = Environment(
        loader=loader,
        autoescape=select_autoescape(enabled_extensions=("j2"))
    )
    template = env.get_template('node-exporter-pod-definition.yml.j2')
    node_exporter_flags = [
        f"--collector.{flag.strip()}"
        for flag in flags.split(",")
    ]

    # Render the template
    manifest = template.render({
        'pod_name': pod_name,
        'node_name': node_name,
        'namespace': namespace,
        'port': port,
        'node_exporter_flags': node_exporter_flags
    })

    yaml = YAML(typ='safe', pure=True)
    manifest_dict = yaml.load(manifest)

    return manifest_dict

async def create_node_exporter_pod(v1: client.CoreV1Api, pod_name: str, node_name: str,flags: str, port: int) -> None:
    # Define the pod spec
    pod_spec = create_node_exporter_pod_spec(pod_name,node_name,flags,port)
    logger.debug(f'Pod spec is {pod_spec}')
    try:
        http_response = v1.create_namespaced_pod(namespace=namespace, body=pod_spec)  # HTTP POST
        logger.info(f"Pod {pod_name} created successfully on node {node_name} in namespace {namespace}.")
    except client.exceptions.ApiException as ex:
        if ex.status == 404:
            logger.error(f"Status 404: Pod creation failed for pod {pod_name} in namespace {namespace}.")
        elif ex.status == 400:
            logger.error(f"Bad request: Failed to create pod {pod_name} in namespace {namespace}.")
            logger.error(traceback.format_exc())
        else:
            logger.error(f"Error creating Pod: {ex.reason} (code: {ex.status})")
            logger.error(traceback.format_exc())
    except Exception as e:
        logger.error(str(e))
    return None

def delete_pod(v1:client.CoreV1Api , pod_name:str) -> None:

    try:
        http_response = v1.delete_namespaced_pod(name = pod_name, namespace= namespace,body = client.V1DeleteOptions(grace_period_seconds = 0))
        print(f'Pod with name {pod_name} from {namespace} namespace has been deleted')

    except client.exceptions.ApiException as e:
        logger.error(traceback.format_exc())
        if e.status == 404:
            print(f'Pod {pod_name} did not deleted. Error 404')
        else:
            print(e)
    return None


async def create_configmap(v1: client.CoreV1Api, configmap_name: str, otel_specs :str , verbose=False) -> client.V1ConfigMap:
    try:
        configmap = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=configmap_name),
            data={"otel-collector-config.yaml": otel_specs}
        )


        # Run the synchronous API call in a separate thread
        created_configmap = v1.create_namespaced_config_map(namespace, configmap)

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
    v1 = get_api_handler()
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

async def deploy_node_exporter_pod(node_name: str, flags: str,port: int) -> bool :

    v1 = get_api_handler()

    logger.debug(f'Node exporter Pod with name:{node_name} is been created')
    final_pod_name = f"node-exporter-{node_name}"
    try:
        await create_node_exporter_pod(v1, final_pod_name, node_name, flags, port)
    except Exception as e:
        logger.error(f'Error creating pod for node {node_name} : {e}')
        logger.error(traceback.format_exc())
        return None,None

    return final_pod_name

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
    v1 = get_api_handler()

    logger.debug(f'OTEL Pod with name:{node_name} is been created')
    final_config_name = f"{base_configmap_name}-{node_name}"
    final_pod_name = f"{base_pod_name}-{node_name}"
    try:
        await create_configmap(v1, final_config_name, otel_yaml)
        await create_pod(v1, final_pod_name, node_name, final_config_name)
    except Exception as e:
        logger.error(f'Error creating pod for node {node_name} : {e}')
        logger.error(traceback.format_exc())
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
    v1 = get_api_handler()

    final_config_name = f"{base_configmap_name}-{node_name}"
    final_pod_name = f"{base_pod_name}-{node_name}"
    try:
        delete_pod(v1, final_pod_name)
        remove_configmap(v1, final_config_name)
    except Exception as e:
        logger.error(f'Error creating pod for node {node_name} : {e}')
        return False

    return True

def delete_node_exporter_pod(node_name: str) -> bool:
    v1 = get_api_handler()

    final_pod_name = f"node-exporter-{node_name}"
    try:
        delete_pod(v1, final_pod_name)
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


def create_svc_manifest(name_prefix=None):
    """Create manifest for service-providing component using Jinja template.
       Returns:
           manifest (str): The rendered service manifest as a string.
       """

    loader = PackageLoader("mlsysops", "templates")
    env = Environment(
        loader=loader,
        autoescape=select_autoescape(enabled_extensions=("j2"))
    )
    template = env.get_template('otel-collector-service.yaml.j2')
    name = "otel-collector"
    if name_prefix is not None:
        name = name_prefix + name
    # Render the template with the context data
    manifest = template.render({
        'name': name,
        'type': "ClusterIP",
        'selector': "otel-collector",
        "otlp_grpc_port": int(os.getenv("MLS_OTEL_GRPC_PORT","43170")),
        "otlp_http_port": int(os.getenv("MLS_OTEL_HTTP_PORT","43180")),
        "otlp_prometheus_port": int(os.getenv("MLS_OTEL_PROM_PORT","9999"))
    })

    yaml = YAML(typ='safe',pure=True)
    manifest_dict = yaml.load(manifest)

    return manifest_dict


async def create_svc(name_prefix=None,svc_manifest=None):
    """Create a Kubernetes service.

    Note: For testing it deletes the service if already exists.

    Args:
        svc_manifest (dict): The Service manifest.

    Returns:
        svc (obj): The instantiated V1Service object.
    """
    core_api = get_api_handler()
    if svc_manifest is None:
        svc_manifest = create_svc_manifest(name_prefix)
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
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
namespace = 'mlsysops-framework'
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
            logger.error("Nodes not found (404).")
        elif e.status == 401:
            logger.error("Unauthorized (401). Check your credentials.")
        else:
            logger.error(f"An error occurred: {e}")
    except Exception as ex:
        logger.error(f"Unexpected error: {ex}")
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
            logger.error(traceback.format_exc())
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
        logger.debug(f'Pod with name {pod_name} from {namespace} namespace has been deleted')

    except client.exceptions.ApiException as e:
        logger.error(traceback.format_exc())
        if e.status == 404:
            logger.error(f'Pod {pod_name} did not deleted. Error 404')
        else:
            logger.error(e)
    return None


async def create_configmap(v1: client.CoreV1Api, configmap_name: str, otel_specs :str , verbose=False) -> client.V1ConfigMap:
    try:
        configmap = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=configmap_name),
            data={"otel-collector-config.yaml": otel_specs}
        )


        # Run the synchronous API call in a separate thread
        created_configmap = v1.create_namespaced_config_map(namespace, configmap)

        logger.debug(f"ConfigMap '{configmap_name}' created in namespace '{namespace}'.")
        return created_configmap

    except client.exceptions.ApiException as e:
        if e.status == 409:
            logger.error(f"ConfigMap '{configmap_name}' already exists in namespace '{namespace}'.")
        elif e.status == 400:
            logger.error(f"Bad request in creating ConfigMap '{configmap_name}' in namespace '{namespace}'.")
        else:
            logger.error(f"Error creating ConfigMap: {e.reason}")
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
        logger.error(ex)
        return None

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
        logger.error(f'Could not redeploy configmap :{configmap_name} in namespace:{namespace} , reason: {ex.reason}')
    except Exception as e:
        logger.error(e)
    return None

async def deploy_node_exporter_pod(node_name: str, flags: str,port: int) -> bool :

    v1 = get_api_handler()

    logger.debug(f'Node exporter Pod with name:{node_name} is been created')
    final_pod_name = f"node-exporter-{node_name}"
    try:
        await create_node_exporter_pod_with_restart(v1, final_pod_name, node_name, flags, port)
    except Exception as e:
        logger.error(f'Error creating pod for node {node_name} : {e}')
        logger.error(traceback.format_exc())
        return None,None

    return final_pod_name

async def create_otel_pod(node_name: str , otel_yaml) -> bool :
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
            namespace=namespace)
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
                namespace=namespace)
            #print(resp)
        except ApiException as exc:
            logger.error('Failed to delete service: %s', exc)
    try:
        svc_obj = core_api.create_namespaced_service(body=svc_manifest,
                                                     namespace=namespace)
        #print(svc_obj)
        return svc_obj
    except ApiException as exc:
        logger.error('Failed to create service: %s', exc)
        return None

async def create_node_exporter_pod_with_restart(v1: client.CoreV1Api, pod_name: str, node_name: str, flags: str, port: int) -> None:
    """
    Checks if a pod already exists. If it exists, deletes the pod and recreates it.
    
    Args:
        v1: Kubernetes CoreV1Api client.
        pod_name: Name of the pod to create or restart.
        node_name: Name of the node where the pod should be created.
        flags: Node exporter flags.
        port: Port for the Node Exporter pod.

    Returns:
        None
    """
    try:
        # Check if the pod already exists
        existing_pod = None
        try:
            existing_pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            logger.info(f"Pod {pod_name} already exists in namespace {namespace}. It will be redeployed.")
        except client.exceptions.ApiException as ex:
            if ex.status == 404:
                logger.info(f"Pod {pod_name} does not exist in namespace {namespace}. Creating a new pod.")
            else:
                logger.error(f"Error while checking pod existence: {ex.reason} (code: {ex.status})")
                logger.error(traceback.format_exc())
                return  # Stop if there are unknown errors during the pod existence check

        # If the pod exists, delete it
        if existing_pod:
            try:
                delete_node_exporter_pod(node_name)
                logger.info(f"Pod {pod_name} deleted successfully.")
            except Exception as e:
                logger.error(f"Error while deleting existing pod {pod_name}: {e}")
                logger.error(traceback.format_exc())
                return  # Stop on delete error

        # Create the node exporter pod
        await create_node_exporter_pod(v1, pod_name, node_name, flags, port)

    except Exception as e:
        logger.error(f"Unexpected error in restarting pod {pod_name} on node {node_name}: {e}")
        logger.error(traceback.format_exc())
    return None

async def create_otel_pod_with_restart(node_name: str, otel_yaml: dict):
    """
    Checks if an OpenTelemetry (OTEL) pod exists. If it does not exist, deletes the associated
    ConfigMap and pod and recreates them.

    Args:
        node_name (str): The name of the node for the OTEL pod.
        otel_yaml (str): The YAML configuration for the OTEL client.

    Returns:
        bool: True if the operation is successful, False otherwise.
    """
    v1 = get_api_handler()

    final_config_name = f"{base_configmap_name}-{node_name}"
    final_pod_name = f"{base_pod_name}-{node_name}"

    try:
        # Check if the OTEL pod already exists
        existing_pod = None
        try:
            existing_pod = v1.read_namespaced_pod(name=final_pod_name, namespace=namespace)
            logger.info(f"OTEL Pod {final_pod_name} already exists in namespace {namespace}. It will be redeployed.")
        except client.exceptions.ApiException as ex:
            if ex.status == 404:
                logger.info(f"OTEL Pod {final_pod_name} does not exist in namespace {namespace}. Creating a new pod.")
            else:
                logger.error(f"Error while checking OTEL pod existence: {ex.reason} (code: {ex.status})")
                logger.error(traceback.format_exc())
                return final_pod_name, final_config_name  # Stop if there are unknown errors during the pod existence check

        # If the pod exists, delete it and its associated ConfigMap
        if existing_pod:
            try:
                logger.info(f"Deleting existing OTEL Pod {final_pod_name} and ConfigMap {final_config_name}.")
                delete_otel_pod(node_name)
                logger.info(f"Deleted OTEL Pod {final_pod_name} and ConfigMap {final_config_name} successfully.")
            except Exception as e:
                logger.error(f"Error while deleting existing OTEL pod {final_pod_name} or ConfigMap {final_config_name}: {e}")
                logger.error(traceback.format_exc())
                return final_pod_name, final_config_name  # Stop on delete error

        # Create the ConfigMap and OTEL pod
        logger.info(f"Creating new OTEL ConfigMap {final_config_name} and Pod {final_pod_name}.")
        await create_configmap(v1, final_config_name, otel_yaml)
        await create_pod(v1, final_pod_name, node_name, final_config_name)
        logger.info(f"Successfully created OTEL ConfigMap {final_config_name} and Pod {final_pod_name}.")

    except Exception as e:
        logger.error(f"Unexpected error while redeploying OTEL pod {final_pod_name} on node {node_name}: {e}")
        logger.error(traceback.format_exc())
        return final_pod_name, final_config_name

    return final_pod_name, final_config_name
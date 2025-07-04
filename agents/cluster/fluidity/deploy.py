"""Fluidity application-deployment helper functionality."""
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

from __future__ import print_function
import copy
import json
import socket
import sys
import logging
from operator import add
import os
import random
import string
import time
import multiprocessing
from kubernetes import client, utils
from kubernetes.utils.create_from_yaml import FailToCreateError
from kubernetes.client.rest import ApiException
from nodes import get_k8s_nodes, get_node_availability, node_provides_resources
from mlsysops.utilities import node_matches_requirements
from mlsysops import MessageEvents
from spade_msg import PodDict, CompDict, EventDict, create_pod_dict 
import cluster_config

from mlsysops.logger_util import logger

def update_host_status(comp_spec, hostname, status):
    for host in comp_spec['hosts']:
        if host['host'] == hostname:
            host['status'] = status


def validate_host(pod_spec, comp_spec, hostname, nodes_list):
    node_desc = None
    for type in nodes_list['mlsysops']:
        # logger.info(f'type {type}')

        for node in nodes_list['mlsysops'][type]:
            # logger.info(f" node {node['metadata']['name']}")

            if node['metadata']['name'] == hostname:
                node_desc = node
                break
            
    if not node_desc or not node_matches_requirements(node_desc, comp_spec['spec']):
        logger.error(f"Node desc for {hostname} does not exist or does not match comp requirements")
        logger.info(node_desc)
        return False
    
    # Check the resources of the first container
    # TODO Use comp_spec
    resources = pod_spec['spec']['containers'][0].get("resources", None)
    if resources:
        logger.info(f'resources {resources}')
        requests = resources.get("requests", None)
        logger.info(f'requests {requests}')
        if requests and not node_provides_resources(hostname, requests, nodes_list['kubernetes']):
            logger.info(f'Asking for resources {resources}')
            logger.error(f"Node {hostname} does not provide requested resources {resources}")
            return False

    return True

def get_random_key(length):
    """Get random key.

    Used to differentiate the different instances of the same component.
    """
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def create_svc_manifest(app_name, app_uid, component, port, proto, external_access):
    """Create manifest for service-providing component.

    Args:
        app_name (str): The Fluidity application name.
        app_uid (str): The Fluidity application unique identifier.
        component (str): The Fluidity component name.
        port (int): The exposed service port.

    Returns:
        manifest (dict): The respective service manifest.
    """
    if proto == None:
        proto = 'TCP'
    if external_access:
        # This Service is visible as <NodeIP>:spec.ports[*].nodePort and .spec.clusterIP:spec.ports[*].port.
        svc_type = 'NodePort'
    else:
        svc_type = 'ClusterIP'
    manifest = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'labels': {
                'mlsysops.eu/app': app_name,
                'mlsysops.eu/component': component
            },
            'name': component
            # 'name': '{}-svc'.format(component)
        },
        'spec': {
            'type': svc_type,
            'ports': [
                {
                    'port': port,
                    'protocol': proto
                }
            ],
            'selector': {
                'mlsysops.eu/app': app_name,
                'mlsysops.eu/component': component
            }
        }
    }
    return manifest


def create_svc_object(app_name, app_uid, component, port, proto, external_access):
    """Create V1Service object for service-providing component.

    Args:
        app_name (str): The Fluidity application name.
        app_uid (str): The Fluidity application unique identifier.
        component (str): The Fluidity component name.
        port (int): The exposed service port.

    Returns:
        svc (obj): The respective V1Service object.
    """

    if proto == None:
        proto = 'TCP'
    if external_access:
        svc_type = 'NodePort'
    else:
        svc_type = 'ClusterIP'

    svc = client.V1Service(
        api_version = 'v1',
        kind = 'Service',
        metadata = client.V1ObjectMeta(
            labels = {
                'mlsysops.eu/app': app_name,
                'mlsysops.eu/component': component
            },
            name = component
        ),
        spec = client.V1ServiceSpec(
            type = svc_type,
            ports = [client.V1ServicePort(
                port = port,
                protocol = proto
            )],
            selector = {
                'mlsysops.eu/app': app_name,
                'mlsysops.eu/component': component
            }
        )
    )

    return svc


def create_svc(svc_manifest):
    """Create a Kubernetes service.

    Note: For testing it deletes the service if already exists.

    Args:
        svc_manifest (dict): The Service manifest.

    Returns:
        svc (obj): The instantiated V1Service object.
    """
    core_api = client.CoreV1Api()
    resp = None

    try:
        logger.info('Trying to read service if already exists')
        resp = core_api.read_namespaced_service(
            name=svc_manifest['metadata']['name'],
            namespace=cluster_config.NAMESPACE)
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
                namespace=cluster_config.NAMESPACE)
        except ApiException as exc:
            logger.error('Failed to delete service: %s', exc)
    
    try:
        svc_obj = core_api.create_namespaced_service(body=svc_manifest,
                                                     namespace=cluster_config.NAMESPACE)
        #print(svc_obj)
        return svc_obj
    except ApiException as exc:
        logger.error('Failed to create service: %s', exc)
        return None

def transform_key(key):
    """Remove underscores and capitalize the next letter."""
    parts = key.split('_')
    return parts[0] + ''.join(part.capitalize() for part in parts[1:])

def transform_dict_keys(d):
    """Recursively transform dictionary keys."""
    if isinstance(d, dict):
        new_dict = {}

        for key, value in d.items():
            new_key = transform_key(key)
            new_dict[new_key] = transform_dict_keys(value)

        return new_dict
    elif isinstance(d, list):
        return [transform_dict_keys(item) for item in d]
    else:
        return d

def create_pod_manifest(comp_spec, old_spec=None):
    """Create manifest for application component.
    Args:
        comp_spec (obj): The Fluidity component specification.
        comp_spec (obj): The previous component specification.
    Returns:
        manifest (dict): The respective Pod manifest.
    """
    manifest = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {
            'name': comp_spec['name']
        },
        'spec': {
            'containers': []
        }
    }

    resources = {}
    resources['requests'] = {'cpu': None, 'memory': None}
    resources['limits'] = {'cpu': None, 'memory': None}

    #logger.info(f'Old spec {old_spec}')
    if 'containers' in comp_spec['spec']:
        for container in comp_spec['spec']['containers']:
            container['name'] = comp_spec['name']
            
            if old_spec:
                for old_container in old_spec['spec']['containers']:
                    if old_container['name'] == container['name']:
                        if 'env' in old_container:
                            container['env'] = old_container['env']

            #logger.info(f'New container {container}')
            temp_dict = copy.deepcopy(container)

            if 'platform_requirements' in temp_dict:
                #logger.info('Parsing platform_requirements')
                container_requirements = temp_dict.pop('platform_requirements', None)
                acceleration_api = temp_dict.pop('acceleration_api', None)

                # if not acceleration_api:
                #     logger.info('No info for acceleration is provided')

                if not container_requirements:
                    continue

                if 'cpu' in container_requirements:
                    if 'requests' in container_requirements['cpu']:
                        resources['requests']['cpu'] = container_requirements['cpu']['requests']
                    if 'limits' in container_requirements['cpu']:
                        resources['limits']['cpu'] = container_requirements['cpu']['limits']
                if 'memory' in container_requirements:
                    if 'requests' in container_requirements['memory']:
                        resources['requests']['memory'] = container_requirements['memory']['requests']
                    if 'limits' in container_requirements['memory']:
                        resources['limits']['memory'] = container_requirements['memory']['limits']                  
                    
                temp_dict['resources'] = resources
                #logger.info('resources %s', resources)
            # The containers field is modified to the official kubernetes field.
            k8s_container = transform_dict_keys(temp_dict)
            #logger.info('new_container %s', k8s_container)
            manifest['spec']['containers'].append(k8s_container)
    
    if old_spec and 'nodeName' in old_spec['spec']:
        manifest['spec']['nodeName'] = old_spec['spec']['nodeName']

    if 'runtime_class_name' in comp_spec['spec']:
        #logger.info('FOUND RUNTIME CLASS')
        manifest['spec']['runtimeClassName'] = comp_spec['spec']['runtime_class_name']

    if 'restart_policy' in comp_spec['spec']:
        manifest['spec']['restartPolicy'] = comp_spec['spec']['restart_policy']
        
    if 'host_network' in comp_spec['spec']:
        manifest['spec']['hostNetwork'] = comp_spec['spec']['host_network']

    return manifest


def create_pod_object(manifest):
    """Create Pod object of component with Fluidity-related info.

    Args:
        manifest (dict): The Pod manifest (template).

    Returns:
        pod (obj): The respective V1Pod object.
    """
    pod = client.V1Pod(
        api_version = 'v1',
        kind = 'Pod',
        metadata = client.V1ObjectMeta(
            labels = manifest['metadata']['labels'],
            name = manifest['metadata']['name']
        ),
        spec = client.V1PodSpec(
            containers = manifest['spec']['containers']
        )
    )
    return pod


def extend_pod_label_template(manifest, app_name, app_uid, comp_name):
    """Extend a component's Pod manifest template with Fluidity-related info.

    Inserts at Pod's metadata field the labels `mlsysops.eu/app`,
    `mlsysops.eu/component` and `mlsysops.eu/componentUID`
    (completed later), specifying the acceptable `mlsysops.eu/node-type` based on
    the placement option and the identifier of the selected candidates.
    Args:
        manifest (dict): The existing Pod manifest (template) that is extended.
        app_name (str): The Fluidity application name.
        app_uid (str): The Fluidity application unique identifier.
        comp_name (str): The Fluidity component name.
    """
    # Add labels section in manifest, if it does not exist
    if 'labels' not in manifest['metadata']:
        manifest['metadata']['labels'] = {}
        
    labels = manifest['metadata']['labels']
    labels['mlsysops.eu/app'] = app_name
    labels['mlsysops.eu/component'] = comp_name
    labels['mlsysops.eu/componentUID'] = None # Inserted during Pod creation

    # Get the spec field
    pod_spec = manifest['spec']

def extend_pod_env_template(manifest, svc_addr):
    """Extend a component's Pod manifest template with svc-related info.
    In case the component invokes another one, it can also set the environment
    variable 'SERVICE_ADDR' to the IP:port of the other component's service
    (assuming that each component invokes a single service).
    Args:
        manifest (dict): The existing Pod manifest (template) that is extended.
        svc_addr (str): The IP:port of the service invoked.
    """
    pod_spec = manifest['spec']
    if svc_addr != None:
        for container in pod_spec['containers']:
            if 'env' not in container:
                container['env'] = []
            container['env'].append({'name': 'SERVICE_ADDR', 'value': svc_addr})

def is_valid_resources_dict(resources):
    """
    Validate the structure and types of a resources dictionary.

    Expected format (flexible):
    resources = {
        'requests': {
            'cpu': '500m',
            'memory': '128Mi',
            ...
        },
        'limits': {
            'cpu': '1',
            'memory': '256Mi',
            ...
        }
    }

    Rules:
    - The top-level object must be a dictionary.
    - 'requests' and 'limits' are optional keys.
    - If present, 'requests' or 'limits' must be dictionaries.
    - Their keys must be strings ('cpu', 'memory').
    - Their values must also be strings (e.g., '500m', '128Mi', '1') or None.

    Parameters:
        resources (dict): The dictionary to validate.

    Returns:
        bool: True if the dictionary matches the expected format, False otherwise.
    """

    if not isinstance(resources, dict):
        return False

    optional_sections = ['requests', 'limits']

    for section in optional_sections:
        if section in resources:
            section_dict = resources[section]

            if not isinstance(section_dict, dict):
                return False

            for key, value in section_dict.items():
                if not isinstance(key, str) or (not isinstance(value, str) and value is not None):
                    return False

    return True


def extend_pod_instance(manifest, pod_name, constraints=None, plan_uid=None):
    """Extend a component's instance Pod manifest with Fluidity-related info.

    Inserts at Pod's metadata field the instance's name and sets the label
    `mlsysops.eu/componentUID` to that name/identifier. In case the component
    invokes a system service, it also sets the environment variables `APP_ID`
    and `COMP_ID` to the respective unique identifiers.

    Args:
        manifest (dict): The existing Pod manifest that is extended.
        pod_name (str): The Fluidity component instance name (unique identifier).
    """
    if 'labels' not in manifest['metadata']:
        manifest['metadata']['labels'] = {}
    manifest['metadata']['name'] = pod_name
    manifest['metadata']['labels']['mlsysops.eu/componentUID'] = pod_name
    
    if plan_uid:
        manifest['metadata']['labels']['mlsysops.eu/planUID'] = plan_uid

    for container in manifest['spec']['containers']:
        if 'resources' in container:
            resources = container['resources']
            logger.info(f'Requested update in resources {resources}')
            
            if not is_valid_resources_dict(resources):
                logger.error(f'resources are not valid {resources}')
                return False

    # logger.debug(f'Updated manifest {manifest}')
    
    return True

def pin_pod_instance(manifest, node_name):
    """Pin a component's instance Pod to a specific node."""
    manifest['spec']['nodeName'] = node_name

def add_related_edge_info(manifest, related_to):
    """Add the host of the interacting edge component instance."""
    manifest['metadata']['labels']['mlsysops.eu/relatedEdgeHost'] = related_to

def create_adjusted_pods_and_configs(app, nodes_list, plan_uid):

    for comp_name in app['components']:
        comp_spec = app['components'][comp_name]
        pod_template = comp_spec['pod_template']
        
        for host in comp_spec['hosts']:
            if host['status'] != 'PENDING':
                continue

            # if not validate_host(pod_template, comp_spec, host['host'], nodes_list):
            #     logger.error(f"Host {host['host']} did not pass eligibility check")
            #     return False

            pod_dict = copy.deepcopy(pod_template)
            uid = get_random_key(8)
            pod_name = '{}-m-{}'.format(comp_name, uid)
            extend_pod_instance(pod_dict, pod_name, plan_uid=plan_uid)
            pin_pod_instance(pod_dict, host['host'])
            comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})
            host['status'] = 'ACTIVE'
    
    return True

def create_pod(app, pod_dict, comp_spec):
    api = client.CoreV1Api()
    
    try:
        api.create_namespaced_pod(body=pod_dict, namespace=cluster_config.NAMESPACE)
        app['total_pods'] +=1
        app['pod_names'].append(pod_dict['metadata']['name'])

        for entry in comp_spec['pod_manifests']:
            if entry['file'] == pod_dict:
                entry['status'] = 'ACTIVE'
    except ApiException as exc:
        logger.error(f"Failed to create Pod {pod_dict['metadata']['name']} with exc: {exc}")
        app['total_pods'] = 0
        app['pod_names'] = []
        return False

    logger.info(f"Current pod list {app['pod_names']}")
    return True

def delete_pod(pod_name, app=None):
    api = client.CoreV1Api()

    try:
        # NOTE: If grace period is not zero and the host is offline, 
        # the pod will continue having Running status after deletion.
        api.delete_namespaced_pod(name=pod_name, namespace=cluster_config.NAMESPACE, 
                                  body=client.V1DeleteOptions(grace_period_seconds=0))
        if app:
            app['total_pods'] -= 1

            if pod_name in app['pod_names']:
                app['pod_names'].remove(pod_name)
            else:
                logger.error(f"Pod {pod_name} is not in pod_names list {app['pod_names']}")

    except ApiException as exc:
        logger.error('Failed to delete Pod: %s', exc)
        return False
    
    return True

def read_pod(pod_name):
    api = client.CoreV1Api()
    resp = None
    
    try:
        resp = api.read_namespaced_pod(name=pod_name, namespace=cluster_config.NAMESPACE)
    except ApiException as exc:
        logger.info('Pod does not exist or has been removed')
    
    return resp

def delete_running_pods(app):
    logger.info('Deleting all running pods for app: %s', app['name'])

    for pod_name in app['pod_names']:
        resp = delete_pod(pod_name)
        
        if not resp:
            return False
        
    return True

def sync_remove_pod(pod_name, host_name):
    """
    The difference with the delete_and_wait_term is that the current function waits until the pod does not exist
    anymore (reading the pod fails). If the node is disconnected, it aborts.
    """
    api = client.CoreV1Api()
    

    resp = delete_pod(pod_name)
    if not resp:
        return False

    while True:
        time.sleep(1)
        nodes = get_k8s_nodes()

        if nodes == [] or get_node_availability(host_name, nodes) == False:
            break

        if not read_pod(pod_name):
            break

def cleanup_pods():
    remove_process_list = []
    api = client.CoreV1Api()

    try:
        pods = api.list_namespaced_pod(namespace=cluster_config.NAMESPACE)
    except ApiException as exc:
        logger.error('Failed to delete Pod: %s', exc)
        return False
    
    pod_list = pods.items

    for pod in pod_list:
        #logger.info('Pod', pod)
        pod_name = pod.metadata.name
        labels = pod.metadata.labels

        if labels == None:
            continue
        
        host_name = pod.spec.node_name
        if 'mlsysops.eu/app' in labels:
            logger.info('Deleting pod with name %s', pod_name)
            logger.info('labels %s', pod.metadata.labels)
            logger.info('Pod has mlsysops.eu/app label.')
            temp_process = multiprocessing.Process(target=sync_remove_pod, args=(pod_name, host_name))
            remove_process_list.append(temp_process)
    
    for process in remove_process_list:
        logger.info('Starting removal process %s', process)
        process.start()
    
    for process in remove_process_list:
        logger.info('Waiting for removal process to terminate %s', process)
        process.join()

    return True

def check_for_hosts_to_delete(app, plan_dict):
    """Checks for unused pods and deletes them."""

    for comp_name in app['components']:
        comp_spec = app['components'][comp_name]
        hosts_to_del = []

        for host in comp_spec['hosts']:
            # Check for host status
            if host['status'] != 'INACTIVE':
                continue

            hosts_to_del.append(host)

            for pod in comp_spec['pod_manifests']:
                pod_dict = pod['file']
                logger.info(f'CHECK FOR HOSTS TO DELETE: pod_dict {pod_dict}')
                if pod_dict['spec']['nodeName'] == host['host']:
                    pod_name = pod_dict['metadata']['name']
                    resp = delete_and_wait_term(pod_name, app)
                    if resp == False:
                        return False

                    plan_dict[comp_name]['specs'][pod_name] = create_pod_dict(
                                                                              pod_dict['spec']['nodeName'], 
                                                                              MessageEvents.COMPONENT_REMOVED.value
                                                                            )

            # Delete pod manifest from components dict
            for entry in list(comp_spec['pod_manifests']):
                if entry['file']['spec']['nodeName'] == host['host']:
                    comp_spec['pod_manifests'].remove(entry)

        for host in hosts_to_del:
            comp_spec['hosts'].remove(host)

    return True


def delete_and_wait_term(pod_name, app):
    logger.info('Deleting pod with name:%s', pod_name)
    nodes = get_k8s_nodes()    

    resp = delete_pod(pod_name, app)
    if not resp:
        return False

    # Check until status is Terminating with sleep(0.1)
    # Also handle exception
    while True:
        resp = read_pod(pod_name)
        
        if not resp or resp.status.phase != "Running" or get_node_availability(resp.spec.node_name, nodes) == False:
            break
        
        time.sleep(0.1)

    logger.info('Deleted pod with name:%s',pod_name)

    return True

def deploy_new_pods(app, plan_dict):
    """Deployment of new pods."""

    for comp_name in app['components']:
        comp_spec = app['components'][comp_name]

        for pod_dict in comp_spec['pod_manifests']:
            if pod_dict['status'] != 'PENDING':
                continue

            if not create_pod(app, pod_dict['file'], comp_spec):
                logger.error('Create pod failed. Returning False')
                return False
            
            pod_name = pod_dict['file']['metadata']['name']
            plan_dict[comp_name]['specs'][pod_name] = create_pod_dict(pod_dict['file']['spec']['nodeName'], 
                                                                      MessageEvents.COMPONENT_PLACED.value, 
                                                                      {'comp_spec':comp_spec,
                                                                      'pod_spec': pod_dict['file']}
                                                                    )

    return True

def check_violated_priority(high, low, priority_list):
    # Assuming single dependency per app 
    high_idx = priority_list.index(high)
    low_idx = priority_list.index(low)

    if low_idx < high_idx:
        temp = priority_list[low_idx]
        priority_list[low_idx] = priority_list[high_idx]
        priority_list[high_idx] = temp

def update_pod_image(api, pod_name, new_img):

    # Get the Pod
    pod = read_pod(pod_name)
    if not pod:
        return False

    # Extract container names
    container_names = [container.name for container in pod.spec.containers]
    container_name = container_names[0]
    logger.info(f"Updating Pod '{pod_name}' with new image: {new_img}")
    logger.info(f"Container name: {container_name}")

    patch = {
        "spec": {
            "containers": [
                {   
                    "name": container_name,
                    "image": new_img
                }
            ]
        }
    }

    try:
        api.patch_namespaced_pod(name=pod_name, namespace=cluster_config.NAMESPACE, body=patch)
    except ApiException as exc:
        logger.error('Failed to patch Pod: %s', exc)
        return False

    return True

def change_comp_spec(app, comp_plan, comp_spec, constraints, nodes_list, plan_uid=None):
    """Update component's Pod spec.
    'change_spec' action modifies the Pod's runtimeClass and resources.
    Args:
        app (dict): The FluidityApp info dictionary.
        comp_plan (dict): Contains the action and the new Pod spec.
        comp_spec (dict): The internal component spec.
    """
    # Steps:
    # (1) Read the new pod Spec and update the Pod template.
    # (2) Deploy the new Pod (with new uid following the comp name).
    # (3) Remove the old Pod.
    # (4) Update the pod name in the list of pod names.
    
    api = client.CoreV1Api()
    updated_spec = None
    pod_to_update = None
    comp_name = comp_spec['name']
    pod_dict = comp_spec['pod_template']

    if comp_name not in app['components']:
        logger.error('Component %s does not belong to app component dict. Continue...', comp_name)
        return False, {}
    
    found = False
    for pod_name in app['pod_names']:
        if pod_name.startswith(comp_name):
            pod_to_update = pod_name
            found = True
            break

    if not found:
        logger.error(f"Did not find {comp_name} in pod list {app['pod_names']}")
   
    if comp_plan['action'] == 'change_spec':
        new_spec = comp_plan['new_spec']
        new_spec['metadata'] = pod_dict['metadata']

        # if not validate_host(new_spec, comp_spec, comp_plan['host'], nodes_list):
        #     logger.error(f"Host {comp_plan['host']} did not pass eligibility check")
        #     return False, {}

        pin_pod_instance(new_spec, comp_plan['host'])

        old_pod_name = pod_to_update
        old_uid = old_pod_name.rsplit("-", 1)[-1]
        new_uid = get_random_key(8)

        while new_uid == old_uid:
            new_uid = get_random_key(8)

        new_pod_name = new_uid.join(old_pod_name.rsplit(old_uid, 1))
        
        # Extend/modify the old template
        if not extend_pod_instance(new_spec, new_pod_name, constraints=constraints, plan_uid=plan_uid):
            logger.error('extend_pod_instance failed')
            return False, {}

        #logger.info(f"new spec {new_spec}")
        resp = create_pod(app, new_spec, comp_spec)
        if not resp:
            return False, {}

        # Delete the old Pod.
        resp = delete_and_wait_term(old_pod_name, app)
        if resp == False:
            return False, {}

        for manifest_entry in comp_spec['pod_manifests']:
            if manifest_entry['file']['metadata']['name'] == old_pod_name:
                manifest_entry['file'] = new_spec

        # Replace old pod name with a new one.
        app['pod_names'] = list(map(lambda x: new_pod_name if x == old_pod_name else x, app['pod_names']))
        comp_spec['pod_template'] = new_spec

    return True, comp_spec['pod_template']

def deploy_app_pods_and_configs(app, nodes_list, plan_uid=None):
    """Deploy Pods and policy configs for all selected component instances.

    Args:
        app (dict): The FluidityApp info dictionary.
        nodes_list (dict): The Fluidity-related node dictionary.

    Returns:
        bool: True if the deployment is successful, False otherwise.
        plan_dict (dict): Key: component name, value: CompDict for each
        component with the respective PodDicts.
    """
    logger.info('Deploy Pods for components of app: %s', app['name'])
    api = client.CoreV1Api()
    initial_deployment = app['curr_plan']['curr_deployment']

    if 'pod_names' not in app:
        app['pod_names'] = []
        app['total_pods'] = 0

    app_spec = app['spec']
    priority_list = [key for key in app['components']]
    deployment_dependency = False

    for comp_name in app['components']:
        comp_spec = app['components'][comp_name]['spec']

        if 'DependsOn' in comp_spec:
            deployment_dependency = True
            low = comp_name
            high = comp_spec['DependsOn'][0]
            check_violated_priority(high, low, priority_list)

    plan_dict = {}

    for priority_entry in priority_list:
        for comp_name in initial_deployment:
            if comp_name != priority_entry or comp_name not in app['components']:
                continue
                
            pod_name = None
            comp_spec = app['components'][comp_name]
            

            logger.info('GOING TO DEPLOY: %s', comp_name)

            if  comp_spec['cluster_id'] != cluster_config.CLUSTER_ID:
                logger.info('Found wrong cluster_id %s for comp %s (correct: %s). Ignoring ...', 
                             comp_spec['cluster_id'], comp_name, cluster_config.CLUSTER_ID)
                continue
            
            plan_dict[comp_name] = copy.deepcopy(CompDict)
            if 'qos_metrics' in comp_spec:
                plan_dict[comp_name]['qos_metrics'] = comp_spec['qos_metrics']

            for instance in initial_deployment[comp_name]:
                if instance['status'] != 'PENDING':
                    continue
                
                logger.info('Valid cluster_id for comp %s. Deploying ...', comp_name)
                logger.info('Comp status: %s',instance['status'])
                
                pod_template = comp_spec['pod_template']
                pod_dict = copy.deepcopy(pod_template)
                uid = get_random_key(8)
                pod_name = '{}-{}'.format(comp_name, uid)
                extend_pod_instance(pod_dict, pod_name, plan_uid=plan_uid)

                # Retrieve the policy developer's desired host from the initial_deployment structure
                host_name = instance['host']
                instance['status'] = 'ACTIVE'
                comp_spec['hosts'] = copy.deepcopy(initial_deployment[comp_name])
                
                # if not validate_host(pod_template, comp_spec, host_name, nodes_list):
                #     logger.error(f"Host {host_name} did not pass eligibility check")
                #     return False, {}
                
                pin_pod_instance(pod_dict, host_name)
                comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})

                resp = create_pod(app, pod_dict, comp_spec)
                if not resp:
                    logger.error(f'Pod {pod_name} not created.')
                    return False, {}
                
                plan_dict[comp_name]['specs'][pod_dict['metadata']['name']] = create_pod_dict(
                                                                                pod_dict['spec']['nodeName'],
                                                                                MessageEvents.POD_ADDED.value,
                                                                                {'comp_spec':comp_spec['spec'],
                                                                                'pod_spec': pod_dict}
                                                                            ) 

            if deployment_dependency == True:
                while True:
                    nodes = get_k8s_nodes()
                    resp = read_pod(pod_name)
                    if not resp:
                        return False, {}

                    logger.info('Waiting for comp %s to start running on %s', pod_name, resp.spec.node_name)

                    if resp.status.phase == "Running" and get_node_availability(resp.spec.node_name, nodes):
                        break
                    elif get_node_availability(resp.spec.node_name, nodes) == False:
                        logger.error('Failed to get node availability. %s', resp.spec.node_name)
                        break

                    time.sleep(0.5)

    return True, plan_dict
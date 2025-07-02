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

#/usr/bin/python3
"""Fluidity nodes functionality."""
from __future__ import print_function
import logging
import os
import sys
import uuid
import operator

from kubernetes import client, config
#from kubernetes.client import ApiClient
from kubernetes.client.rest import ApiException
from objects_api import FluidityObjectsApi, FluidityApiException
from util import human_to_byte, cpu_human_to_cores
from uuid import UUID
import cluster_config
from cluster_config import API_GROUP, VERSION

from mlsysops.logger_util import logger


def update_resource(name, spec, resource, nodes):
    logger.info(f"Updating resource {resource} with name {name}")
    # If node with the same name exists, replace it.
    # Otherwise append it to the list.
    if resource == 'Node':
        api_client = client.ApiClient()
        node_obj = api_client._ApiClient__deserialize(spec, "V1Node")

        for i, node in enumerate(nodes['kubernetes']):
            if node.metadata.name == name:
                nodes['kubernetes'][i] = node_obj
                return
        nodes['kubernetes'].append(node_obj)
    elif resource == 'mlsysopsnodes':
        layer = spec.get('continuum_layer', 'generic')
        for i, node in enumerate(nodes['mlsysops'][layer]):
            if node.get("metadata", {}).get("name") == name:
                nodes['mlsysops'][layer][i] = spec
                return
        nodes['mlsysops'][layer].append(spec)

def delete_resource(name, spec, resource, nodes):
    logger.info(f"Deleting resource {resource} with name {name}")
    # Find the name of node and delete it 
    if resource == 'Node':
        nodes[:] = [node for node in nodes if node.get("metadata", {}).get("name") != name]
        logger.info(f'Removed node {name}, curr list: {nodes}')
    elif resource == 'mlsysopsnodes':
        layer = spec.get('continuum_layer', 'generic')
        node_list = nodes['mlsysops'][layer]
        node_list[:] = [node for node in node_list if node.get("metadata", {}).get("name") != name]
        logger.info(f'Removed node {name}, curr list: {node_list}')

def append_host_to_list(entry_dict, hosts, remove=False):
    """Appends host dictionary in the component's host list with the modified host status
    (if not already stored).

    Args:
        entry_dict (dict): dictionary to be added/modified
        hosts (list): component host list.

    Returns:
        void
    """
    #found = False
    for host in hosts:
        if host['host'] == entry_dict['host']:
            host['status'] = entry_dict['status']
            return True
    
    if remove:
        return False
    
    # At this point we did not find the entry, so we append it to the list.
    hosts.append(entry_dict)

def get_node_internal_ip(node_name):
    """Get the cluster-internal IP of a node.

    Args:
        node_name (str): The node's name.

    Returns:
        str: The IPv6 address.
    """
    node_address = None
    v1 = client.CoreV1Api()
    node = v1.read_node(node_name)
    for addr in node.status.addresses:
        if addr.type == 'InternalIP':
            node_address = addr.address
    return node_address

def node_provides_resources(node_name, target, nodes_list):
    """Check if resource requests of component(s) fit at a node.

    Args:
        node_name (str): The name of the node.
        target (dict): Target resources (cpu, memory).

    Returns:
        bool: True, if the node can provide these resources, False otherwise
    """

    node_exists = False
    logger.info(node_name)

    for node in nodes_list:
        if node.metadata.name == node_name:
            node_exists = True
            logger.debug('Check resources - node exists: %s', node_name)
    
    if not node_exists:
        logger.error('Node does not exist.')
        return False

    core_api = client.CoreV1Api()
    node = core_api.read_node(node_name)
    # status = node.status
    allocatable = node.status.allocatable
    
    if target['cpu']:
        allocatable_cpu = cpu_human_to_cores(allocatable['cpu'])
        target_cpu = cpu_human_to_cores(target['cpu'])
        if allocatable_cpu < target_cpu:
            logger.info('Check resources - node does not have cpu: %s', node_name)
            return False

    if target['memory']:
        allocatable_memory = human_to_byte(allocatable['memory'])
        target_memory = human_to_byte(target['memory'])
        if allocatable_memory < target_memory:
            logger.info('Check resources - node does not have memory: %s', node_name)
            return False

    logger.info('Check resources - node provides resources: %s', node_name)
    return True

def cmp_fields(comp_field, node_field, op, resource):
    if comp_field and (not node_field or op(comp_field, node_field)):
        logger.error(f"{resource}: Node field {node_field} does not match comp requirement: {comp_field}")
        return False
    return True

def node_matches_requirements(node, comp_spec):
    """Check if node matches description-related requirements.

    Args:
        node (dict): The MLSysOpsNode description.
        comp_spec (dict): A component's extended spec.

    Returns:
        bool: True, if the node matches the requirements, False otherwise
    """
    logger.info(f"Checking requirements for node: {node['metadata']['name']}")
    node_name = node.get("metadata").get("name")
    placement = comp_spec.get("node_placement", None)
    logger.info(f"node {node}")
    if placement:
        host = placement.get("node", None)

        if host and host != node_name:
            logger.error(f"Selected host {node_name} does not match description-related host {host}")
            return False

        node_layer = placement.get("continuum_layer", None)
        if node_layer and "*" not in node_layer:
            if 'continuum_layer' not in node:
                logger.error(f"Node {node_name} does not have continuum_layer")
                return False
            match_layer = False
            for layer in node_layer:
                if layer == node['continuum_layer']:
                    match_layer = True
                    break

            if not match_layer:
                logger.error(f"Node {node} does not match node layer")
                return False

        mobility = placement.get("mobile", False)
        if mobility and not node.get("mobile", False):
            logger.error(f"Node {node_name} is not mobile")
            return False

        comp_labels = placement.get("labels", None)
        logger.info(f"comp_labels {comp_labels}")

        node_labels = node.get("labels", None)
        logger.info(f"node_labels {node_labels}")

        if comp_labels:
            
            if not node_labels:
                logger.error(f"Node {node_name} does not match comp labels {comp_labels}")
                return False

            for label in comp_labels:
                if label not in node_labels:
                    logger.error(f"Node {node_name} does not match comp label {label}")
                    return False
    
    sensors = comp_spec.get("sensors", None)
    if sensors:
        for sensor in sensors:
            camera = sensor.get("camera", None)
            if camera:
                node_camera = None
                for node_sensor in node['sensors']:
                    if 'camera' in node_sensor:
                        node_camera = node_sensor['camera']
                        break

                if not node_camera:
                    logger.error(f"Node does not have camera sensor")
                    return False

                if not cmp_fields(camera.get("model", None), node_camera.get("model", None), operator.ne, "camera model"):
                    return False

                if not cmp_fields(camera.get("camera_type", None), node_camera.get("camera_type", None), operator.ne, "camera type"):
                    return False

                if not cmp_fields(camera.get("minimum_framerate", None), node_camera.get("framerate", None), operator.gt, "camera framerate"):
                    return False

                resolution = camera.get("resolution", None)
                node_resolutions = node_camera.get("supported_resolutions", [])
                if resolution and resolution not in node_resolutions:
                    logger.error(f"Node does not match camera resolution requirements")
                    return False

            temperature = sensor.get("temperature", None)
            if temperature:
                node_temperature = None
                for node_sensor in node['sensors']:
                    if 'temperature' in node_sensor:
                        node_temperature = node_sensor['temperature']
                        break
                
                if not node_temperature:
                    logger.error(f"Node does not have temperature sensor")
                    return False

                if not cmp_fields(temperature.get("model", None), node_temperature.get("model", None), operator.ne, "temperature model"):
                    return False
    node_env = node.get("environment", None)
    if  not cmp_fields(comp_spec.get("node_type", None), node_env.get("node_type", None), operator.ne, "node type"):
        return False

    if not cmp_fields(comp_spec.get("os", None), node_env.get("os", None), operator.ne, "os"):
        return False
    
    container_runtime = comp_spec.get("container_runtime", None)
    node_container_runtimes = node_env.get("container_runtime", [])
    if container_runtime and container_runtime not in node_container_runtimes:
        logger.error(f"Node does not match container runtime requirements")
        return False
        
    # NOTE: We assume single container components
    container = comp_spec.get("containers")[0]
    #logger.info(f"comp_spec {comp_spec}")
    platform_requirements = container.get("platform_requirements")
    if platform_requirements:
        cpu = platform_requirements.get("cpu", None)
        node_hw = node.get("hardware", None)
        if cpu:
            node_cpu = node_hw.get("cpu", None)
            cpu_arch_list = cpu.get("architecture", None)
            if cpu_arch_list and not node_cpu:
                logger.error(f"Node does not have cpu arch info")
                return False
            
            node_cpu_arch = node_cpu.get("architecture", None)
            if (cpu_arch_list and not node_cpu_arch) or (node_cpu_arch and node_cpu_arch not in cpu_arch_list):
                logger.error(f"Node {node_cpu_arch} does not have any of the required cpu architectures {cpu_arch_list}")
                return False

            cpu_freq = cpu.get("frequency", None)
            if cpu_freq and not node_cpu:
                logger.error(f"Node does not have cpu freq info")
                return False

            node_cpu_freq = node_cpu.get("frequency", [])
            if cpu_freq:
                found = False
                for freq in node_cpu_freq:
                    if cpu_freq <= freq:
                        found = True
                        break

                if not found:
                    logger.error(f"Node does not have cpu freq equal to or greater than the requested")
                    return False

            cpu_perf = cpu.get("performance_indicator", None)
            if cpu_perf and not node_cpu:
                logger.error(f"Node does not have cpu perf info")
                return False
            
            if not cmp_fields(cpu_perf, node_cpu.get("performance_indicator", None), operator.gt, "cpu perf indicator"):
                return False

        
        if not cmp_fields(platform_requirements.get("disk", None), node_hw.get("disk", None), operator.gt, "disk"):
            return False

        gpu = platform_requirements.get("gpu", None)
        if gpu:
            node_gpu = node_hw.get("gpu", None)
            gpu_model = gpu.get("model", None)
            if gpu_model and not node_gpu:
                logger.error(f"Node does not have gpu info")
                return False

            if not cmp_fields(gpu_model, node_gpu.get("model", None), operator.ne, "gpu model"):
                return False

            gpu_mem = gpu.get("memory", None)
            if gpu_mem and not node_gpu:
                logger.error(f"Node does not have gpu info")
                return False
            
            if not cmp_fields(gpu_mem, node_gpu.get("memory", None), operator.gt, "gpu memory"):
                return False

            gpu_perf = gpu.get("performance_indicator", None)
            if gpu_perf and not node_gpu:
                logger.error(f"Node does not have gpu info")
                return False

            if not cmp_fields(gpu_perf, node_gpu.get("performance_indicator", None), operator.gt, "gpu perf indicator"):
                return False

    return True


def get_custom_nodes(node_type_plural, label_selector):
    """Currently used to get all types of nodes represented via CRDs
    
    Returns:
        list: The list of node dictionaries based on the given node_type
    """
    cr_api = FluidityObjectsApi()
    try:
        crs = cr_api.list_fluidity_object(node_type_plural, label_select='node-type={}'.format(label_selector))
    except FluidityApiException:
        logger.error('Retrieving %s failed', node_type_plural)
        return []
    return crs['items']

def get_mls_nodes(node_plural, type):
    """Get all types of MLSysOpsNodes
    
    Returns:
        list: The list of node dictionaries based on the given node_plural
    """
    # Create dynamic client for CRDs
    api = client.CustomObjectsApi()
    node_list = []

    # List all CRs
    try:
        crs = api.list_namespaced_custom_object(API_GROUP, VERSION, cluster_config.NAMESPACE, node_plural)
    except ApiException as exc:
        logger.error('List node CRs failed: %s', exc)
        return []

    # Filter based on spec.continuum_layer
    for item in crs['items']:
        layer = item.get('continuum_layer', None)
        if type == 'generic' and layer is None:
            node_list.append(item)
        elif layer == type:
            node_list.append(item)
           
    return node_list

def get_node_availability(node_name, nodes):
    for node in nodes:
        if node.metadata.name == node_name:
            for condition in node.status.conditions:
                if condition.type == 'Ready':
                    if condition.status == 'True':
                        logger.info('%s node has Ready status.', node_name)
                        return True
                    else:
                        logger.info('%s is not online. Returning False.', node_name)
                        return False
    return False

def get_k8s_nodes():
    """Get the list of k8s node objects.

    Returns:
        list: The nodes dictionaries.
    """
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()
    api_instance = client.CoreV1Api()
    try:
        node_list = api_instance.list_node()
    except ApiException as exc:
        logger.error('List node failed: %s', exc)
        return []
    return node_list.items

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

    logger.debug('Check resources - node provides resources: %s', node_name)
    return True

def cmp_fields(comp_field, node_field, op, resource):
    if comp_field and (not node_field or op(comp_field, node_field)):
        logger.error(f"{resource}: Node field {node_field} does not match comp requirement: {comp_field}")
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

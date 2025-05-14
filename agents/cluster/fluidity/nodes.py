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
import sys

from kubernetes import client, config
# from kubernetes import config, watch
from kubernetes.client.rest import ApiException
# from ruamel.yaml import YAML

# from fluidity_crds_api  import register_all_fluidity_crd, FluidityCrdsApiException
# from fluidity_crds_config import CRDS_INFO_LIST, API_GROUP
from objects_api import FluidityObjectsApi, FluidityApiException
from objects_util import get_crd_info


logger = logging.getLogger(__name__)

def get_app_desc(app_name):
    """Get the Fluidity app k8s object.

    Returns:
        dict: The fluidityapp description.
    """
    crd_info = get_crd_info('fluidityapps')[1]
    cr_api = FluidityObjectsApi()
    app = cr_api.get_fluidity_object('fluidityapps', app_name)

def update_app_resources(app_name, resource_list):
    """Update the FluidityApp updatedResources field
    
    Returns:
        True in case of success,
        otherwise False.
    """
    cr_api = FluidityObjectsApi()
    app_desc = cr_api.get_fluidity_object('fluidityapps', app_name)
    app_desc['updatedResources'] = resource_list
    try:
        cr_api.update_fluidity_object('fluidityapps', app_name, app_desc)
    except FluidityApiException:
        logger.error('Updating updatedResources failed')
        return False
    return True

def get_custom_nodes(node_type_plural, label_selector):
    """Currently used to get all types of nodes represented via CRDs
    
    Returns:
        list: The list of node dictionaries based on the given node_type
    """
    # Indicative usage below
    # crs = cr_api.list_fluidity_object('cloudnodes', label_select='node_type=cloud')
    cr_api = FluidityObjectsApi()
    try:
        crs = cr_api.list_fluidity_object(node_type_plural, label_select='node-type={}'.format(label_selector))
    except FluidityApiException:
        logger.error('Retrieving %s failed', node_type_plural)
        return []
    return crs['items']


def get_cloudnodes():
    """Get the list of Fluidity cloudnodes k8s objects.
    Returns:
        list: The cloudnodes dictionaries.
    """
    crd_info = get_crd_info('cloudnodes')[1]
    cr_api = FluidityObjectsApi()
    try:
        crs = cr_api.list_fluidity_object(crd_info['plural'])
    except FluidityApiException:
        logger.error('Retrieving %s failed', crd_info['kind'])
    
    return crs['items']

def get_drones():
    """Get the list of Fluidity drone k8s objects.

    Returns:
        list: The drones dictionaries.
    """
    crd_info = get_crd_info('drones')[1]
    cr_api = FluidityObjectsApi()
    try:
        crs = cr_api.list_fluidity_object(crd_info['plural'])
    except FluidityApiException:
        logger.error('Retrieving %s failed', crd_info['kind'])
    # Return the custom resource instances list
    # cr_list = []
    # for cri in crs['items']:
    #     cr_item = {
    #         'name': cri['metadata']['name'],
    #         'uid': cri['metadata']['uid'],
    #         'spec': cri['spec']
    #     }
    #     cr_list.append(cr_item)
    return crs['items']


def get_edgenodes():
    """Get the list of Fluidity edgenode k8s objects.

    Returns:
        list: The edgenodes dictionaries.
    """
    crd_info = get_crd_info('edgenodes')[1]
    cr_api = FluidityObjectsApi()
    try:
        crs = cr_api.list_fluidity_object(crd_info['plural'])
    except FluidityApiException:
        logger.error('Retrieving %s failed', crd_info['kind'])
    # Return the custom resource instances list
    return crs['items']

def get_mobilenodes():
    """Get the list of Fluidity mobilenode k8s objects.

    Returns:
        list: The mobilenodes dictionaries.
    """
    crd_info = get_crd_info('mobilenodes')[1]
    cr_api = FluidityObjectsApi()
    try:
        crs = cr_api.list_fluidity_object(crd_info['plural'])
    except FluidityApiException:
        logger.error('Retrieving %s failed', crd_info['kind'])
    # Return the custom resource instances list
    return crs['items']

def get_dronestations():
    """Get the list of Fluidity dronestation k8s objects.

    Returns:
        list: The dronestations dictionaries.
    """
    crd_info = get_crd_info('dronestations')[1]
    cr_api = FluidityObjectsApi()
    try:
        crs = cr_api.list_fluidity_object(crd_info['plural'])
    except FluidityApiException:
        logger.error('Retrieving %s failed', crd_info['kind'])
    # Return the custom resource instances list
    return crs['items']


# def map_drone_to_station(drones, dronestations):
#     """Map drone objects to dronestation objects."""
#     pass


def get_node_availability(node_name, nodes):
    #logger.info(nodes)
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

def get_k8s_nodes():
    """Get the list of k8s node objects.

    Returns:
        list: The nodes dictionaries.
    """
    config.load_kube_config()
    api_instance = client.CoreV1Api()
    try:
        node_list = api_instance.list_node()
    except ApiException as exc:
        logger.error('List node failed: %s', exc)
        return []
    #logger.info(node_list.items)
    return node_list.items


def set_node_label(node_name, label, value):
    """Add/update a specific label to a k8s node object.

    Args:
        node_name (str): The name of the node.
        label (str): The label to add or update.
        value (str): The value to set.
    """
    api_instance = client.CoreV1Api()
    body = {
        'metadata': {
            'labels': {
                '{}'.format(label): '{}'.format(value)}
        }
    }
    # Patch the node label
    try:
        api_response = api_instance.patch_node(node_name, body)
        logger.debug('Set node label: %s', api_response)
    except ApiException as exc:
        logger.error('Setting node label failed: %s', exc)


def remove_node_label(node_name, label):
    """Remove a specific label from a k8s node object.

    Args:
        node_name (str): The name of the node.
        label (str): The label to add or update.
    """
    api_instance = client.CoreV1Api()
    body = {
        'metadata': {
            'labels': {
                '{}'.format(label): None}
        }
    }
    try:
        api_response = api_instance.patch_node(node_name, body)
        logger.debug('Remove node label: %s', api_response)
    except ApiException as exc:
        logger.error('Removing node label failed: %s', exc)


def set_node_annotation(node_name, key, value):
    """Attach a specific annotation to a k8s node object.

    Args:
        node_name (str): The name of the node.
        key (str): The annotation's key.
        value (str): The value to set.
    """
    api_instance = client.CoreV1Api()
    body = {
        'metadata': {
            'annotations': {
                '{}'.format(key): '{}'.format(value)}
        }
    }
    try:
        api_response = api_instance.patch_node(node_name, body)
        logger.debug('Set node annotation: %s', api_response)
    except ApiException as exc:
        logger.error('Setting node annotation failed: %s', exc)


def remove_node_annotation(node_name, key):
    """Remove a specific annotation to a k8s node object.

    Args:
        node_name (str): The name of the node.
        key (str): The annotation to remove.
    """
    api_instance = client.CoreV1Api()
    body = {
        'metadata': {
            'annotations': {
                '{}'.format(key): None}
        }
    }
    try:
        api_response = api_instance.patch_node(node_name, body)
        logger.debug('Remove node label: %s', api_response)
    except ApiException as exc:
        logger.error('Removing node annotation failed: %s', exc)


def set_mobile_label(mobile_name, label, value):
    """Add/update a specific label to a Fluidity mobile k8s object.

    Args:
        mobile_name (str): The name of the mobile node.
        label (str): The label to add or update.
        value (str): The value to set.
    """
    cr_api = FluidityObjectsApi()
    mobile = cr_api.get_fluidity_object('mobilenodes', mobile_name)
    # Ensure labels field exists at metadata section
    if 'labels' not in mobile['metadata']:
        mobile['metadata']['labels'] = {}
    labels = mobile['metadata']['labels']
    labels[label] = value
    try:
        cr_api.update_fluidity_object('mobilenodes', mobile_name, mobile)
    except FluidityApiException:
        logger.error('Updating mobile label failed')

def set_drone_label(drone_name, label, value):
    """Add/update a specific label to a Fluidity drone k8s object.

    Args:
        drone_name (str): The name of the drone.
        label (str): The label to add or update.
        value (str): The value to set.
    """
    cr_api = FluidityObjectsApi()
    drone = cr_api.get_fluidity_object('drones', drone_name)
    # Ensure labels field exists at metadata section
    if 'labels' not in drone['metadata']:
        drone['metadata']['labels'] = {}
    labels = drone['metadata']['labels']
    labels[label] = value
    try:
        cr_api.update_fluidity_object('drones', drone_name, drone)
    except FluidityApiException:
        logger.error('Updating drone label failed')

# Modified to satisfy the fluiditynode type.
def set_fluiditynode_label(fluiditynode_name, label, value):
    """Add/update a specific label to a Fluidity fluidity k8s object.

    Args:
        fluiditynode_name (str): The name of the node.
        label (str): The label to add or update.
        value (str): The value to set.
    """
    cr_api = FluidityObjectsApi()
    node = cr_api.get_fluidity_object('fluiditynodes', fluiditynode_name)
    # Ensure labels exists at metadata section
    if 'labels' not in node['metadata']:
        node['metadata']['labels'] = {}
    labels = node['metadata']['labels']
    labels[label] = value
    try:
        cr_api.update_fluidity_object('fluiditynodes', fluiditynode_name, node)
    except FluidityApiException:
        logger.error('Updating fluiditynode label failed')


if __name__ == '__main__':
    # Configure logging
    logger = logging.getLogger('')
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s '
                                  '[%(filename)s] %(message)s')
    f_hdlr = logging.FileHandler('/var/tmp/Fluidity_nodes.log')
    f_hdlr.setFormatter(formatter)
    f_hdlr.setLevel(logging.DEBUG)
    logger.addHandler(f_hdlr)
    s_hdlr = logging.StreamHandler(sys.stdout)
    s_hdlr.setFormatter(formatter)
    s_hdlr.setLevel(logging.DEBUG)
    logger.addHandler(s_hdlr)
    logger.setLevel(logging.DEBUG)
    get_nodes()

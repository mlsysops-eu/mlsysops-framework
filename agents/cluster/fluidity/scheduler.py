"""FluidityApp scheduler module."""
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

import json
import logging
import random
import threading
import time

from kubernetes import client, config, watch

from objects_api import FluidityObjectsApi, FluidityApiException
#from fluidityapp_settings import MAX_COVERAGE, switch_start
import settings
from util import sort_linked_list, human_to_byte
from config import get_adhoc_info, get_node_internal_ip, send_notification_to_host
# from operation_area import get_com_area_edgenode
# from human_bytes import HumanBytes


logger = logging.getLogger(__name__)

PROXY_PORT = 9527

info_adhoc = {
    'msg-type': 'adhoc-info',
    'ssid': '',
    'locus-ip': '',
    'pod-name': '',
    'pass': '..........'
}

#: str: Name of the custom scheduler
SCHEDULER_NAME = 'fluidityapp-scheduler'


def available_cloud_nodes(nodes_list):
    """Get the available cloud nodes.
    
    Returns:
        list of str: The names of cloud nodes.
    """
    #config.load_kube_config()
    core_api = client.CoreV1Api()
    ready = []
    #logger.info('***About to print all node names')
    for n in nodes_list:
        logger.info(n.metadata.name)
        if n.metadata.labels['mlsysops.eu/node-type'] != 'cloud':
            continue
        node = core_api.read_node(n.metadata.name)
        for status in node.status.conditions:
            if status.type == 'Ready' and status.status == 'True':
                ready.append(n.metadata.name)
    logger.info('Available cloud nodes: %s', ready)
    return ready


def node_provides_resources(node_name, target, nodes_list):
    """Check if resource requests of component(s) fit at a node.

    Args:
        node_name (str): The name of the node.
        target (dict): Target resources (cpu, memory).

    Returns:
        bool: True, if the node can provide these resources, False otherwise
    """
    node_exists = False
    print(node_name)
    for node in nodes_list:
        if node.metadata.name == node_name:
            node_exists = True
            logger.debug('Check resources - node exists: %s', node_name)
    if not node_exists:
        logger.error('Node does not exist.')
        return False

    # config.load_kube_config()
    core_api = client.CoreV1Api()
    node = core_api.read_node(node_name)
    # status = node.status
    allocatable = node.status.allocatable
    allocatable_cpu = float(allocatable['cpu'])
    allocatable_memory = human_to_byte(allocatable['memory'])
    if allocatable_cpu < target['cpu']:
        logger.info('Check resources - node does not have cpu: %s', node_name)
        return False
    if allocatable_memory < target['memory']:
        logger.info('Check resources - node does not have memory: %s', node_name)
        return False
    logger.info('Check resources - node provides resources: %s', node_name)
    return True


def node_matches_requirements(node, comp_spec):
    """Check if node matches service and other Fluidity-related requirements.

    Args:
        node (dict): The drone/edgenode k8s object.
        comp_spec (dict): A component's extended spec.

    Returns:
        bool: True, if the node can provide these resources, False otherwise
    """
    logger.info('Checking requirements for node:%s',node['metadata']['name'])
    if 'systemServices' in comp_spec:
        logger.info('Checking systemService requirements')
        if 'systemServices' not in node['spec']:
            logger.info('Node does not provide systemServices')
            return False
        if 'mobility' in comp_spec['systemServices']:
            logger.info('Checking mobility service requirements')
            if 'mobility' not in node['spec']['systemServices']:
                return False
            for method in comp_spec['systemServices']['mobility']['methods']:
                if method not in node['spec']['systemServices']['mobility']['methods']:
                    return False
            if 'autopilot' in comp_spec['systemServices']['mobility']:
                if 'autopilot' not in node['spec']['systemServices']['mobility']:
                    return False
                if comp_spec['systemServices']['mobility']['autopilot'] != node['spec']['systemServices']['mobility']['autopilot']:
                    return False
            if 'maxSpeed' in comp_spec['systemServices']['mobility']:
                if comp_spec['systemServices']['mobility']['maxSpeed'] > node['spec']['systemServices']['mobility']['maxSpeed']:
                    return False
            if 'maxAltitude' in comp_spec['systemServices']['mobility']:
                if comp_spec['systemServices']['mobility']['maxAltitude'] > node['spec']['systemServices']['mobility']['maxAltitude']:
                    return False
            if 'maxFlightTime' in comp_spec['systemServices']['mobility']:
                if comp_spec['systemServices']['mobility']['maxFlightTime'] > node['spec']['systemServices']['mobility']['maxFlightTime']:
                    return False
            if 'maneuvering' in comp_spec['systemServices']['mobility']:
                if 'maneuvering' not in node['spec']['systemServices']['mobility']:
                    return False
                for maneuver in comp_spec['systemServices']['mobility']['maneuvering']:
                    if maneuver not in node['spec']['systemServices']['mobility']['maneuvering']:
                        return False
        if 'camera' in comp_spec['systemServices']:
            logger.info('Checking camera service requirements')
            if 'camera' not in node['spec']['systemServices']:
                return False
            for method in comp_spec['systemServices']['camera']['methods']:
                if method not in node['spec']['systemServices']['camera']['methods']:
                    return False
            if 'sensorType' in comp_spec['systemServices']['camera']:
                if comp_spec['systemServices']['camera']['sensorType'] != node['spec']['systemServices']['camera']['sensorType']:
                    return False
            if 'model' in comp_spec['systemServices']['camera']:
                if 'model' not in node['spec']['systemServices']['camera']:
                    return False
                if comp_spec['systemServices']['camera']['model'] != node['spec']['systemServices']['camera']['model']:
                    return False
            if 'maxHorizontalResolution' in comp_spec['systemServices']['camera']:
                if comp_spec['systemServices']['camera']['maxHorizontalResolution'] > node['spec']['systemServices']['camera']['maxHorizontalResolution']:
                    return False
            if 'maxVerticalResolution' in comp_spec['systemServices']['camera']:
                if comp_spec['systemServices']['camera']['maxVerticalResolution'] > node['spec']['systemServices']['camera']['maxVerticalResolution']:
                    return False
    if 'otherResources' in comp_spec:
        logger.info('Checking other resource requirements')
        if 'accelerator' not in node['spec']:
            return False
        for resource in comp_spec['otherResources']:
            if resource == 'DISK':
                continue
            if resource not in node['spec']['accelerator']:
                return False
    if comp_spec['spec']['placement'] == 'edge' and node['spec']['myfeature'] == 'NOTOK':
        logger.info('EdgeNode has myfeature: NOTOK')
        return False
    return True


def select_mobile_host(comp_spec, mobilenodes_list, nodes_list):
    """Select mobile for hosting mobile component.

    Args:
        comp_spec (dict): The extended spec of the mobile component.
        mobilenodes_list (list): The mobile k8s objects.
        nodes_list (list): The node k8s objects.

    Returns:
        bool: True, if host found, False otherwise
    """
    if comp_spec['candidates'] == []:
        logger.error('Candidates not found for mobile component.')
        return
    # select the first candidate for simplicity
    candidate = comp_spec['candidates'][0]
    if not candidate:
        logger.error('Candidate not found.')
        return False
    for mobile in mobilenodes_list:
        found = False
        if mobile['metadata']['name'] == candidate:
            found = True
            break
    if not found:
        logger.error('Mobile node object not found.')
        return False
    node_exists = False
    for node in nodes_list:
        if node.metadata.name == candidate:
            node_exists = True
            logger.debug('Select mobile host - node exists: %s', candidate)
    if not node_exists:
        logger.error('Node object not found.')
        return False
    host = candidate
    if {'name':candidate,'status':'ACTIVE'} not in comp_spec['hosts']:
        comp_spec['hosts'] = [{"name":host,"status": "PENDING"}]
    return True

def select_drone_host(app, drones_list, nodes_list):
    """Select drone for hosting all drone components.

    Args:
        app (dict): The application info dictionary.
        drones_list (list): The drone k8s objects.
        nodes_list (list): The node k8s objects.

    Returns:
        bool: True, if host found, False otherwise
    """
    host = None
    # Since candidates are sorted select the first feasible one
    for candidate in app['drone_candidates']:
        # Check candidate for computing resources
        req = node_provides_resources(candidate,
                                      app['drone_resources_requests'],
                                      nodes_list)
        if not req:
            continue
        for drone in drones_list:
            if drone['metadata']['name'] == candidate:
                drone_obj = drone
                break
        # Check candidate for service and other resources
        for comp_name in app['drone_comp_names']:
            comp_spec = app['components'][comp_name]
            req = node_matches_requirements(drone_obj, comp_spec)
            if not req:
                break
        if not req:
            continue
        host = candidate
    if host is None:
        logger.warning('No host found for drone components - Discarding app')
        return False
    for comp_name in app['drone_comp_names']:
        comp_spec = app['components'][comp_name]
        if {'name':candidate,'status':'ACTIVE'} not in comp_spec['hosts']:
            comp_spec['hosts'] = [{"name":host,"status":"PENDING"}]
    logger.info('Drone host: %s', host)
    return True


def select_edge_hosts(comp_spec, edgenodes_list, nodes_list):
    """Select edgenode(s) for hosting a static edge component.

    Args:
        comp_spec (dict): The extended spec of the edge component.
        edgenodes_list (list): The edgenode k8s objects.
        nodes_list (list): The node k8s objects.

    Returns:
        bool: True, if host(s) found, False otherwise
    """
    edge_locs = comp_spec['staticLocations']
    for edge_loc in edge_locs:
        if edge_loc['instances'] == '*':
            max_instances = len(edge_loc['candidates'])
        else:
            max_instances = int(edge_loc['instances'])
        active_hosts = 0
        for entry in edge_loc['hosts']:
            if entry['name'] not in edge_loc['candidates']:
                logger.info('Host with name %s is not a candidate anymore.', entry['name'])
                entry['status'] = 'INACTIVE'
                # Also mark INACTIVE in comp_spec['hosts'] list
                for entry2 in comp_spec['hosts']:
                    if entry2['name'] == entry['name']:
                        entry2['status'] = 'INACTIVE'
                        break
            elif entry['status'] != 'INACTIVE':
                active_hosts += 1
        for candidate in edge_loc['candidates']:
            # Check candidate for computing resources
            req = node_provides_resources(candidate,
                                          comp_spec['resources_requests'],
                                          nodes_list)
            if not req:
                logger.info('Candidate does not provide resources')
                if {'name':candidate,'status':'ACTIVE'} in comp_spec['hosts']:
                    logger.info('Making candidate INACTIVE')
                    for entry in comp_spec['hosts']:
                        if entry['name'] == candidate:
                            entry['status'] = 'INACTIVE'
                    for entry in edge_loc['hosts']:
                        if entry['name'] == candidate:
                            entry['status'] = 'INACTIVE'
                    active_hosts -= 1
                continue
            print('Going to print edgenodes_list')
            for edgenode in edgenodes_list:
                print(edgenode['metadata']['name'])
                if edgenode['metadata']['name'] == candidate:
                    edgenode_obj = edgenode
                    break
            # Check candidate for service and other resources
            req = node_matches_requirements(edgenode_obj, comp_spec)
            if not req:
                logger.info('Candidate does not match requirements')
                if {'name':candidate,'status':'ACTIVE'} in comp_spec['hosts']:
                    for entry in comp_spec['hosts']:
                        if entry['name'] == candidate:
                            entry['status'] = 'INACTIVE'
                    for entry in edge_loc['hosts']:
                        if entry['name'] == candidate:
                            entry['status'] = 'INACTIVE'
                    active_hosts -= 1
                continue
            if {'name':candidate,'status':'ACTIVE'} not in comp_spec['hosts']:
                comp_spec['hosts'].append({'name':candidate,'status':'PENDING'})
                edge_loc['hosts'].append({'name':candidate,'status':'PENDING'})
                active_hosts += 1
        if active_hosts > max_instances:
            legal = 0
            # TODO: Delete the last (active_hosts - max_instances) elements from hosts 
            # having status PENDING or ACTIVE
            # if status = ACTIVE, make INACTIVE
            # if status = PENDING, delete
            for entry in edge_loc['hosts']:
                if legal < max_instances and entry['status'] != 'INACTIVE':
                    legal += 1
                elif legal == max_instances:
                    if entry['status'] == 'ACTIVE':
                        # Mark as INACTIVE
                        pass
                    elif entry['status'] == 'PENDING':
                        # Delete from list
                        pass
                    active_hosts -= 1

                
    if active_hosts == 0:
        logger.warning('No host found for edge component: %s',
                       comp_spec['name'])
        return False
    logger.info('Edge hosts (%s): %s', comp_spec['name'], comp_spec['hosts'])
    return True


def select_hybrid_to_mobile_hosts(comp_spec, app, edgenodes_list, nodes_list):
    """Select edgenode(s) for hosting edge instances of a hybrid to mobile component.

    Args:
        comp_spec (dict): The extended spec of the hybrid to mobile component.
        app (dict): The application info dictionary.
        edgenodes_list (list): The edgenode k8s objects.
        nodes_list (list): The node k8s objects.

    Returns:
        bool: True, if host(s) found, False otherwise
    """
    #print('start is ', start)
    found_host = False
    old_host_name = None
    previous_host_is_edge = False
    # Check for INACTIVE hosts
    for entry in comp_spec['hosts']:
        # If the node is not a cloud node
        if entry['name'] != comp_spec['host_hybrid_cloud']:
            if entry['name'] not in comp_spec['candidates']:
                #logger.info('Host with name %s is not a candidate anymore.', entry['name'])
                entry['status'] = 'INACTIVE'
                previous_host_is_edge = True
                print('The previous host was an edge node.')
                #end = time.perf_counter()
                #elapsed = end - start
                #logger.info('(INACTIVE Status) Decision delay = %0.10f', elapsed)
                #logger.info('Host with name %s is not a candidate anymore.', entry['name'])
            else:
                old_host_name = entry['name']
    for candidate in comp_spec['candidates']:
        # Check if node provides resources and matches requirements
        # If yes mark as host
        # Check candidate for computing resources
        req = node_provides_resources(candidate,
                                          comp_spec['resources_requests'],
                                          nodes_list)
        if not req:
            logger.info('Candidate does not provide resources')
            if {'name':candidate,'status':'ACTIVE'} in comp_spec['hosts']:
                logger.info('Making candidate INACTIVE')
                for entry in comp_spec['hosts']:
                    if entry['name'] == candidate:
                        entry['status'] = 'INACTIVE'
            continue
        #print('Going to print edgenodes_list')
        for edgenode in edgenodes_list:
            #print(edgenode['metadata']['name'])
            if edgenode['metadata']['name'] == candidate:
                edgenode_obj = edgenode
                break
        # Check candidate for service and other resources
        req = node_matches_requirements(edgenode_obj, comp_spec)
        if not req:
            #logger.info('Candidate does not match requirements')
            if {'name':candidate,'status':'ACTIVE'} in comp_spec['hosts']:
                for entry in comp_spec['hosts']:
                    if entry['name'] == candidate:
                        entry['status'] = 'INACTIVE'
                        #end = time.perf_counter()
                        #elapsed = end - start
                        #logger.info('(INACTIVE Status) Decision delay = %0.10f', elapsed)
            continue
        if {'name':candidate,'status':'ACTIVE'} not in comp_spec['hosts']:
            # TODO: send notification to mobile node to connect to adhoc
            # NOTE: Also check if the old host is an edge node. If true,
            # the notification will be sent after the removal of the old Pod.
            comp_spec['hosts'].append({'name':candidate,'status':'PENDING'})
            #if previous_host_is_edge == False:
            #    result = get_adhoc_info(comp_spec['hosts'][0]['name'], edgenodes_list)
            #    if result['direct-comm'] == True:
            #        mobile_comp_name = app['mobile_comp_names'][0]
            #        mobile_name_host = app['components'][mobile_comp_name]['hosts'][0]['name']
            #        mobile_host_ip = get_node_internal_ip(mobile_name_host)
                    #logger.info('mobile host %s', mobile_host_ip)
            #        info_adhoc['ssid'] = result['ssid']
            #        info_adhoc['locus-ip'] = result['locus-ip']
            #        info_adhoc['pod-name'] = app['pod_names'][-1]
            #        send_notification_to_host(mobile_host_ip, PROXY_PORT, info_adhoc)
            #end = time.perf_counter()
            #elapsed = end - start
            #logger.info('(PENDING Status) Decision delay = %0.10f', elapsed)
        found_host = True
    if old_host_name != None:
        host_exists = False
        if {'name':old_host_name,'status':'ACTIVE'} in comp_spec['hosts']:
            host_exists = True
        # Remove new hosts and keep old one
        if host_exists:
            for entry in list(comp_spec['hosts']):
                if entry['name'] == comp_spec['host_hybrid_cloud']:
                    continue
                if entry['name'] != old_host_name and entry['status'] == 'PENDING':
                    logger.info('Keeping the old host.')
                    comp_spec['hosts'].remove({'name':entry['name'],'status':'PENDING'})
    #logger.info('After scheduler: hosts = %s', comp_spec['hosts'])
    #end = time.perf_counter()
    #elapsed = end - start
    #logger.info('Decision delay = %0.10f', elapsed)
    return found_host
        

def select_hybrid_to_edge_hosts(comp_spec, app, edgenodes_list, nodes_list):
    """Select edgenode(s) for hosting edge instances of a hybrid to edge component.

    Args:
        comp_spec (dict): The extended spec of the hybrid to edge component.
        app (dict): The application info dictionary.
        edgenodes_list (list): The edgenode k8s objects.
        nodes_list (list): The node k8s objects.

    Returns:
        bool: True, if host(s) found, False otherwise
    """
    # Iterate over all interacting static edge components
    for related_comp in comp_spec['hybridHeuristic']['relatedTo']:
        # Ignore not edge components
        if related_comp not in app['edge_comp_names']:
            continue
        related_spec = app['components'][related_comp]
        related_hosts_dict = related_spec['hosts']
        # Iterate over all edge nodes selected to host the interacting
        # static edge component
        for edgenode in related_hosts_dict:
            edge_entry = comp_spec['candidates_hybrid_edge'][related_comp][edgenode]['name']
            # Find first feasible candidate (list already sorted)
            for candidate in edge_entry['candidates']:
                # Check candidate for computing resources
                req = node_provides_resources(candidate,
                                              comp_spec['resources_requests'],
                                              nodes_list)
                if not req:
                    continue
                for tmp_edgenode in edgenodes_list:
                    if tmp_edgenode['metadata']['name'] == candidate:
                        edgenode_obj = tmp_edgenode
                        break
                # Check candidate for service and other resources
                req = node_matches_requirements(edgenode_obj, comp_spec)
                if not req:
                    continue
                edge_entry['host'] = candidate
                comp_spec['hosts'].append({'name':candidate,'status':'PENDING'})
                comp_spec['hosts_hybrid_edge'].append(candidate)
                comp_spec['related_hosts_hybrid_edge'].append(edgenode['name'])
                break
    return True


def _rm_and_sort_cand(comp_spec, op_area=None):
    """Remove first edge candidate for hybrid to drone component and
    sort the list by coverage.
    """
    removed_area = comp_spec['candidates_hybrid_drone_intersection'][0]
    del comp_spec['candidates_hybrid_drone'][0]
    del comp_spec['candidates_hybrid_drone_coverage'][0]
    del comp_spec['candidates_hybrid_drone_intersection'][0]

    if op_area is not None:
        idx = 0
        for candidate in comp_spec['candidates_hybrid_drone']:
            # Intersection with remaining drone operation area
            intersection = comp_spec['candidates_hybrid_drone_intersection'][idx].difference(removed_area)
            comp_spec['candidates_hybrid_drone_intersection'][idx] = intersection
            comp_spec['candidates_hybrid_drone_coverage'][idx] = intersection.area/op_area.area
            logger.info('Recalculating hybrid drone candidate: %s coverage: %f (%f)',
                candidate,
                intersection.area,
                intersection.area/op_area.area)
            idx += 1
    # Sort candidates by coverage (higher is better)
    sorted_candidates = sort_linked_list(comp_spec['candidates_hybrid_drone'],
                                         comp_spec['candidates_hybrid_drone_coverage'],
                                         reverse=True)
    sorted_intersection = sort_linked_list(comp_spec['candidates_hybrid_drone_intersection'],
                                           comp_spec['candidates_hybrid_drone_coverage'],
                                           reverse=True)
    comp_spec['candidates_hybrid_drone_coverage'].sort()
    comp_spec['candidates_hybrid_drone'] = sorted_candidates
    comp_spec['candidates_hybrid_drone_intersection'] = sorted_intersection


def select_hybrid_to_drone_hosts(comp_spec, app, edgenodes_list, nodes_list):
    """Select edgenode(s) for hosting edge instances of a hybrid to drone component.

    Args:
        comp_spec (dict): The extended spec of the hybrid to drone component.
        app (dict): The application info dictionary.
        edgenodes_list (list): The edgenode k8s objects.
        nodes_list (list): The node k8s objects.

    Returns:
        bool: True, if host(s) found, False otherwise
    """
    remaining_op_area = app['drone_op_area']
    covered_op_area = None
    covered_ratio = 0.0
    while covered_ratio < MAX_COVERAGE and comp_spec['candidates_hybrid_drone']:
        # Check best candidate for computing resources (already sorted list)
        req = node_provides_resources(comp_spec['candidates_hybrid_drone'][0],
                                      comp_spec['resources_requests'],
                                      nodes_list)
        if not req:
            _rm_and_sort_cand(comp_spec)
        for edgenode in edgenodes_list:
            if edgenode['metadata']['name'] == comp_spec['candidates_hybrid_drone'][0]:
                edgenode_obj = edgenode
                break
        # Check candidate for service and other resources
        req = node_matches_requirements(edgenode_obj, comp_spec)
        if not req:
            _rm_and_sort_cand(comp_spec)
        comp_spec['hosts'].append({'name':comp_spec['candidates_hybrid_drone'][0],'status':'PENDING'})
        comp_spec['hosts_hybrid_drone'].append(comp_spec['candidates_hybrid_drone'][0])
        comp_spec['hosts_hybrid_drone_intersection'].append(comp_spec['candidates_hybrid_drone_intersection'][0])
        comp_spec['hosts_hybrid_drone_coverage'].append(comp_spec['candidates_hybrid_drone_coverage'][0])
        # Remove achieved coverage from operation area
        remaining_op_area = remaining_op_area.difference(comp_spec['candidates_hybrid_drone_intersection'][0])
        if covered_op_area is None:
            covered_op_area = comp_spec['candidates_hybrid_drone_intersection'][0]
        else:
            covered_op_area = covered_op_area.union(comp_spec['candidates_hybrid_drone_intersection'][0])
        _rm_and_sort_cand(comp_spec, remaining_op_area)
        covered_ratio = covered_op_area.area / app['drone_op_area'].area
    logger.info('Selected hybrid to drone hosts: %s, coverage: %f',
        comp_spec['hosts_hybrid_drone'], covered_ratio)
    return True


def select_cloud_hosts(comp_spec, cloudnodes_list, nodes_list):
    """Select cloud hosts for instances of hybrid and cloud components.

    Returns:
        bool: True, if host(s) found, False otherwise.
    """
    #candidates = available_cloud_nodes(nodes_list)
    instances = 0
    #instances = len(comp_spec['hosts'])
    #if 'cloudReplicas' in comp_spec and instances == comp_spec['cloudReplicas']:
    #    return True
    #if 'cloudReplicas' not in comp_spec and instances > 0:
    #    return True
    for candidate in cloudnodes_list:
        candidate_name = candidate['metadata']['name']
        req = node_provides_resources(candidate_name,
                                      comp_spec['resources_requests'],
                                      nodes_list)
        if not req:
            print('Does not provide resources')
            #if candidate in comp_spec['hosts']:
                # mark to delete
            continue
        instances +=1
        if {'name':candidate_name,'status':'ACTIVE'} not in comp_spec['hosts']:
            comp_spec['hosts'].append({'name':candidate_name,'status':'PENDING'})
        if comp_spec['placement'] == 'hybrid':
            if comp_spec['host_hybrid_cloud'] == None:
                comp_spec['host_hybrid_cloud'] = candidate_name
            break
        else:
            if 'cloudReplicas' not in comp_spec:
                break
            elif instances == comp_spec['cloudReplicas']:
                break
    if instances == 0:
        return False
    return True


def select_hosts(app, mobilenodes_list, drones_list, edgenodes_list, cloudnodes_list, nodes_list):
    """Select hosts for application components.

    Args:
        app (dict): The application info dictionary.
        mobilenodes_list (list): The mobile node k8s objects
        drones_list (list): The drone k8s objects.
        edgenodes_list (list): The edgenode k8s objects.
        nodes_list (list): The node k8s objects.

    Returns:
        bool: True, if hosts found, False otherwise
    """

    # Mobile components
    if app['mobile_comp_names']:
        # NOTE: We assume 1 mobile component
        comp_name = app['mobile_comp_names'][0]
        comp_spec = app['components'][comp_name]
        found = select_mobile_host(comp_spec, mobilenodes_list, nodes_list)
        app['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        if not found and comp_spec['cluster_id'] == fluidityapp_settings.cluster_id:
            logger.info('Not found and cluster id == settings.cluster_id')
            return False
    # Drone components
    if app['drone_comp_names']:
        found = select_drone_host(app, drones_list, nodes_list)
        app['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        if not found:
            return False
    # Edge components
    for comp_name in app['edge_comp_names']:
        comp_spec = app['components'][comp_name]
        found = select_edge_hosts(comp_spec, edgenodes_list, nodes_list)
        app['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        if not found and comp_spec['cluster_id'] == fluidityapp_settings.cluster_id:
            return False
    # Hybrid to static edge components
    for comp_name in app['hybrid_edge_comp_names']:
        comp_spec = app['components'][comp_name]
        found = select_hybrid_to_edge_hosts(comp_spec, app, edgenodes_list, nodes_list)
        app['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        if not found and comp_spec['cluster_id'] == fluidityapp_settings.cluster_id:
            return False
        found = select_cloud_hosts(comp_spec, cloudnodes_list, nodes_list)
        app['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        if not found and comp_spec['cluster_id'] == fluidityapp_settings.cluster_id:
            return False
    # Hybrid to mobile components
    for comp_name in app['hybrid_mobile_comp_names']:
        comp_spec = app['components'][comp_name]
        found = select_hybrid_to_mobile_hosts(comp_spec, app, edgenodes_list, nodes_list)
        app['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        #fluidityapp_settings.switch_start = time.perf_counter()
        if not found:
            logger.info('None of the edge nodes hosts hybrid component.')
            logger.info('Checking for cloud hosts.')
            found = select_cloud_hosts(comp_spec, cloudnodes_list, nodes_list)
            if not found and comp_spec['cluster_id'] == fluidityapp_settings.cluster_id:
                logger.info('Hybrid: Host not found and cluster id == settings.cluster_id')
                return False
        elif comp_spec['host_hybrid_cloud']:
            logger.info('Found edge host for hybrid component.')
            logger.info('Making cloud host INACTIVE')
            # Check for cloud component to mark as INACTIVE (if any)
            cloud_name = comp_spec['host_hybrid_cloud']
            for entry in comp_spec['hosts']:
                if entry['name'] == cloud_name:
                    entry['status'] = 'INACTIVE'
                    app['curr_plan']['curr_deployment'][comp_name][entry['name']] = 'INACTIVE'
                    comp_spec['host_hybrid_cloud'] = None
                    break
    # Hybrid to drone components
    for comp_name in app['hybrid_drone_comp_names']:
        comp_spec = app['components'][comp_name]
        found = select_hybrid_to_drone_hosts(comp_spec, app, edgenodes_list, nodes_list)
        app['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        if not found:
            return False
        found = select_cloud_hosts(comp_spec, cloudnodes_list, nodes_list)
        app['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        if not found:
            return False
    # Cloud components
    for comp_name in app['cloud_comp_names']:
        logger.info('Cloud component')
        logger.info(comp_name)
        comp_spec = app['components'][comp_name]
        found = select_cloud_hosts(comp_spec, cloudnodes_list, nodes_list)
        app['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        if not found and comp_spec['cluster_id'] == fluidityapp_settings.cluster_id:
            return False
    return app['curr_plan']['curr_deployment']


def schedule_all_components(app):
    """Schedule all instances of the application components.

    Args:
        app (dict): The application info dictionary.
    """
    config.load_kube_config()
    api = client.CoreV1Api()
    stream = watch.Watch().stream(api.list_namespaced_pod, 'default')
    scheduled_pods = 0
    for pod in stream:
        if (pod['object'].status.phase == 'Pending'
            and pod['object'].spec.scheduler_name == SCHEDULER_NAME):
            try:
                scheduled_pods +=1
                logger.info('Scheduling %s', pod['object'].metadata.name)
                if pod['object'].spec.node_selector['mlsysops.eu/node-type'] in ['drone', 'edge']:
                    node = pod['object'].spec.node_name
                else:
                    node = random.choice(available_cloud_nodes)
                logger.info('Selected host: %s', node)
                body = client.V1Binding()
                target = client.V1ObjectReference()
                target.kind = 'Node'
                target.apiVersion = 'v1'
                target.name = node
                meta = client.V1ObjectMeta()
                meta.name = pod['object'].metadata.name
                body.target = target
                body.metadata = meta
                resp = api.create_namespaced_binding(pod['object'].metadata.name, 'default', body)
                # Wait for Pod to be initialized and runningpod
                while True:
                    try:
                        resp = api.read_namespaced_pod(name=pod['object'].metadata.name,
                                                       namespace='default')
                    except ApiException as exc:
                        logger.error('Error reading pod %s', exc)
                        break
                    if resp.status.phase != 'Pending':
                        break
                    time.sleep(1)
                logger.info('%s started', pod['object'].metadata.name)
                if scheduled_pods == app['total_pods']:
                    return
            except client.rest.ApiException as exc:
                print(json.loads(exc.body)['message'])

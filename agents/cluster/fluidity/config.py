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

# Create networking and policy configurations for application components
import copy
import json
import logging
import socket
import uuid
from uuid import UUID

import shapely
from kubernetes import client
from kubernetes.client.rest import ApiException

from nodes import get_custom_nodes
from settings import PROXIMITY_THRESHOLD, POLICY_PORT_MOBILITY, POLICY_PORT_CAMERA
from objects_api import FluidityObjectsApi, FluidityApiException
from objects_util import get_crd_info
from geo_util import coords_to_shapely, feature_to_shapely


logger = logging.getLogger(__name__)


policy_config_template = {
    "policies_array": []
}

def get_adhoc_info(name, edgenodes_list):
    tmp_struct = {
        'direct-comm': False,
        'ssid': '',
        'locus-ip': ''
    }

    for entry in edgenodes_list:
        if entry['metadata']['name'] == name:
            for resource in entry['spec']['networkResources']:
                if resource['interface'] == 'WiFi' and resource['connectionType'] == 'direct':
                    tmp_struct['direct-comm'] = True
                    tmp_struct['locus-ip'] = resource['ipAddress']
                    tmp_struct['ssid'] = resource['pairingInfo']['networkId']
                    return tmp_struct

    return tmp_struct

def send_notification_to_host(host_addr, port, msg):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host_addr, port))
        info = copy.deepcopy(msg)
        snd_data = bytes(json.dumps(info), 'UTF-8')
        sock.send(snd_data)
        recv_data = sock.recv(1024)
        received = json.loads(recv_data.decode('UTF-8'))
        logger.info('Sent: %s', snd_data)
        logger.info('Received: %s', received)
    finally:
        sock.close()

def append_dict_to_list(entry_dict, hosts):
    """Appends host dictionary in the component's host list with the modified host status
    (if not already stored).

    Args:
        entry_dict (dict): dictionary to be added/modified
        hosts (list): component host list.

    Returns:
        void
    """

    for host in hosts:
        if host['host'] == entry_dict['host']:
            host['status'] = entry_dict['status']
            return
    # At this point we did not find the entry, so we append it to the list.
    hosts.append(entry_dict)

def get_uuid():
    # string representation of the uid
    uid = uuid.uuid4().hex
    return uid


def uuid_to_hex(uid):
    """Transform uuid4 with dashes to hex.

    Args:
        uuid (str): UUID with dashes

    Returns:
        str: hex of uuid4
    """
    return UUID(uid).hex


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


def send_policy_config(ip, port, fname):
    """Read policies from file and register them.

    Args:
        ip (str): The node's IP address.
        port (int): The policies registration server port.
        fname (str): Filename of the policies file.

    Returns:
        bool: The operation's status. True for success, False otherwise.
    """
    status = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    try:
        with open(fname, 'r') as json_f:
            request = json.load(json_f)

            snd_data = bytes(json.dumps(request), 'UTF-8')
            sock.send(snd_data)
            recv_data = sock.recv(1024)

            received = json.loads(recv_data.decode('UTF-8'))
            if 'status' in received:
                if received['status'] == 'Success':
                    status = True
    except IOError:
        logger.error('Policies file not in current dir (%s).', fname)

    sock.close()
    return status


def send_net_config(ip, port, fname):
    """Read net configuration from file and register them.

    Args:
        ip (str): The node's IP address.
        port (int): The policies registration server port.
        fname (str): Filename of the policies file.

    Returns:
        bool: The operation's status. True for success, False otherwise.
    """
    status = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    try:
        with open(fname, 'r') as json_f:
            request = json.load(json_f)

            snd_data = bytes(json.dumps(request), 'UTF-8')
            sock.send(snd_data)
            recv_data = sock.recv(1024)

            received = json.loads(recv_data.decode('UTF-8'))
            if 'status' in received:
                if received['status'] == 'Success':
                    status = True
    except IOError:
        logger.error('Net config file not in current dir (%s).', fname)

    sock.close()
    return status


def create_access_control(service, kind, methods, app_uid, comp_uid):
    """Create AccessControl policy.

    Args:
        service (str): The type of service (mobility/camera).
        kind (int): The kind of access (grant/deny).
        methods (list of str): The related service methods.
        app_uid (str): Application's unique identifier.
        comp_uid (str): Component's unique identifier.

    Returns:
        dict: The created policy.
    """
    uid = get_uuid()
    policy = {
        'uid': uid,
        'class': service,
        'policyType': 'accessControl',
        'accessControlPolicy': {
            'kind': kind,
            'methods': methods
        },
        'appSelector': [
            {
            'appUID': app_uid,
            'componentUID': comp_uid
            }
        ]
    }
    return policy


def create_geofence_control(app, comp_spec):
    """Create inclusion GeofenceControl policies.

    Args:
        app (dict): The FluidityAppInfo dictionary.
        comp_spec (dict): Component's extended specification.

    Returns:
        dict: The created policy.
    """
    area = {
        'type': 'Feature',
        'properties': {
            'name': 'operationArea',
            'shape': 'Polygon'
        },
        'geometry': json.dumps(shapely.geometry.mapping(app['drone_op_area']))
    }
    uid = get_uuid()
    policy = {
        'uid': uid,
        'class': 'mobility',
        'policyType': 'geofenceControl',
        'accessControlPolicy': {
            'kind': 'inclusion',
            'action': 'discard'
        },
        'areaSelector': area,
        'appSelector': [
            {
            'appUID': app['uid'],
            'componentUID': comp_spec['uid']
            }
        ]
    }
    return policy
    # for ctrl_point in comp_spec['controlPoints']:
    #     if ctrl_point['navigationType'] == 'regionBased':
    #         area = ctrl_point['navigationArea']
    #     elif ctrl_point['navigationType'] == 'pathBased':
    #         # TODO: buffer the path and return the feature
    #     uid = get_uuid()
    #     policy = {
    #         'uid': uid,
    #         'class': 'mobility',
    #         'policyType': 'geofenceControl',
    #         'accessControlPolicy': {
    #             'kind': 'inclusion',
    #             'action': 'discard'
    #         },
    #         'areaSelector': area,
    #         'appSelector': [
    #             {
    #             'appUID': app['uid'],
    #             'componentUID': comp_spec['uid']
    #             }
    #         ]
    #     }
    #     policies.append(policy)
    # return policies


def check_drone_selector(pol_spec, drone_spec):
    """Check if a policy applies to drone.

    Args:
        pol_spec (dict): The policy resource spec field.
        drone_spec (dict): The drone resource spec field.

    Returns:
        bool: True if policy is applicable, False otherwise.
    """
    applies = True
    # If selector is specified, all conditions must apply
    if 'droneSelector' in pol_spec:
        for selector in pol_spec['droneSelector']:
            key = selector['key']
            if key in ['mobilityType', 'model', 'class']:
                # Ignore if not specified by drone
                if key not in drone_spec:
                    continue
                if selector['operator'] == 'In':
                    if drone_spec[key] not in selector['values']:
                        applies = False
                        break
                if selector['operator'] == 'NotIn':
                    if drone_spec[key] in selector['values']:
                        applies = False
                        break
            elif key in ['height', 'length', 'width']:
                if selector['operator'] == 'Gt':
                    if drone_spec['physicalFeatures']['dimensions'][key] <= int(selector['values'][0]):
                        applies = False
                        break
                if selector['operator'] == 'Lt':
                    if drone_spec['physicalFeatures']['dimensions'][key] >= int(selector['values'][0]):
                        applies = False
                        break
            elif key == 'mtom':
                if selector['operator'] == 'Gt':
                    if drone_spec['physicalFeatures']['mtom'] <= int(selector['values'][0]):
                        applies = False
                        break
                if selector['operator'] == 'Lt':
                    if drone_spec['physicalFeatures']['mtom'] >= int(selector['values'][0]):
                        applies = False
                        break
    return applies


def check_edgenode_selector(pol_spec, node_spec):
    """Check if a policy applies to an edgenode.

    Args:
        pol_spec (dict): The policy resource spec field.
        drone_spec (dict): The edgenode resource spec field.

    Returns:
        bool: True if policy is applicable, False otherwise.
    """
    applies = True
    # If selector is specified, all conditions must apply
    if 'edgenodeSelector' in pol_spec:
        for selector in pol_spec['edgenodeSelector']:
            key = selector['key']
            if key in ['model', 'accelerator']:
                # Ignore if not specified by edgenode
                if key not in node_spec:
                    continue
                if selector['operator'] == 'In':
                    if node_spec[key] not in selector['values']:
                        applies = False
                        break
                if selector['operator'] == 'NotIn':
                    if node_spec[key] in selector['values']:
                        applies = False
                        break
    return applies

def check_app_selector(pol_spec, app_uid, comp_uid):
    """Check if a policy applies to drone.

    Args:
        pol_spec (dict): The policy resource spec field.
        app_uid (str): Application's unique identifier.
        comp_uid (str): Component's unique identifier.

    Returns:
        bool: True if policy is applicable, False otherwise.
    """
    applies = True
    # If selector is specified, at least one must apply
    if 'appSelector' in pol_spec:
        applies = False
        for selector in pol_spec['appSelector']:
            # if all(x in selector for x in ['appUID', 'componentUID']):
            if 'appUID' in selector and 'componentUID' in selector:
                if selector['appUID'] == app_uid and selector['componentUID'] == comp_uid:
                    applies = True
                    break
            elif 'appUID' in selector:
                if selector['appUID'] == app_uid:
                    applies = True
                    break
            elif 'componentUID' in selector:
                if selector['componentUID'] == app_uid:
                    applies = True
                    break
    return applies


def add_app_selector(pol_spec, app_uid, comp_uid):
    """Add appSelector field to the policy config.

    Args:
        pol_spec (dict): The policy resource spec field.
        app_uid (str): Application's unique identifier.
        comp_uid (str): Component's unique identifier.
    """
    app_selector = {
        'appUID': app_uid,
        'componentUID': comp_uid
    }
    pol_spec['appSelector'] = [app_selector]


def check_drone_area_selector(pol_spec, op_area, check_proximity=False):
    """Check if a policy applies to drone's operation area.

    Args:
        pol_spec (dict): The policy resource spec field.
        op_area (obj): Calculated drone operation area.
        check_proximity (bool): Flag to check for proximity to drone's
         operation area.

    Returns:
        bool: True if policy is applicable, False otherwise.
    """
    applies = True
    # If selector is specified, op area must intersect with policy's area
    if 'areaSelector' in pol_spec:
        applies = False
        pol_geom = feature_to_shapely(pol_spec['areaSelector'])
        # intersection = pol_geom.intersection(op_area)
        # if intersection.area > 0:
        if pol_geom.intersects(op_area):
            applies = True
        elif check_proximity:
            if pol_geom.distance(op_area) <= PROXIMITY_THRESHOLD:
                applies = True
    return applies


def check_edge_area_selector(pol_spec, node_loc):
    """Check if a policy applies to an edge node.

    Args:
        pol_spec (dict): The policy resource spec field.
        op_area (obj): The node's location.

    Returns:
        bool: True if policy is applicable, False otherwise.
    """
    applies = True
    # If selector is specified, location must be inside policy's area
    if 'areaSelector' in pol_spec:
        applies = False
        # node_loc = edgenode['spec']['location']
        point = coords_to_shapely(node_loc[0], node_loc[1])
        pol_geom = feature_to_shapely(pol_spec['areaSelector'])
        # if pol_geom.contains(point):
        if point.within(pol_geom):
            applies = True
    return applies


def get_limit_control(app, comp_uid, drone_name):
    """Retrieve LimitControl policies.

    Args:
        app (dict): The FluidityAppInfo dictionary.
        comp_uid (str): Component's unique identifier.
        drone_name (str): The drone's name.

    Returns:
        list of dict: The list of related policies.
    """
    cr_api = FluidityObjectsApi()
    try:
        drones = cr_api.list_fluidity_object('drones')
    except FluidityApiException:
        logger.error('Drones retrieval failed')
        return []
    drone_spec = None
    for drone in drones['items']:
        if drone['metadata']['name'] == drone_name:
            drone_spec = drone['spec']
    if drone_spec is None:
        logger.error('Host drone not found')
        return []
    try:
        crs = cr_api.list_fluidity_object('policies')
    except FluidityApiException:
        logger.error('Policies retrieval failed')
        return []

    policies = []
    for cr in crs['items']:
        if cr['spec']['policyType'] != 'limitControl':
            continue
        applies = check_drone_selector(cr['spec'], drone_spec)
        if not applies:
            continue
        applies = check_app_selector(cr['spec'], app['uid'], comp_uid)
        if not applies:
            continue
        applies = check_drone_area_selector(cr['spec'], app['drone_op_area'])
        if not applies:
            continue
        policy_copy = copy.deepcopy(cr['spec'])
        add_app_selector(policy_copy, app['uid'], comp_uid)
        uid = get_uuid()
        policy_copy['uid'] = uid
        policies.append(policy_copy)
    return policies


def get_geofence_control(app, comp_uid, drone_name):
    """Retrieve exclusion GeofenceControl policies.

    Args:
        app (dict): The FluidityAppInfo dictionary.
        comp_uid (str): Component's unique identifier.
        drone_name (str): The drone's name.

    Returns:
        list of dict: The list of related policies.
    """
    cr_api = FluidityObjectsApi()
    try:
        drones = cr_api.list_fluidity_object('drones')
    except FluidityApiException:
        logger.error('Drones retrieval failed')
        return []
    drone_spec = None
    for drone in drones['items']:
        if drone['metadata']['name'] == drone_name:
            drone_spec = drone['spec']
    if drone_spec is None:
        logger.error('Host drone not found')
        return []
    try:
        crs = cr_api.list_fluidity_object('policies')
    except FluidityApiException:
        logger.error('Policies retrieval failed')
        return []

    policies = []
    for cr in crs['items']:
        if cr['spec']['policyType'] != 'geofenceControl':
            continue
        if cr['spec']['geofenceControlPolicy']['kind'] != 'exclusion':
            continue
        applies = check_drone_selector(cr['spec'], drone_spec)
        if not applies:
            continue
        applies = check_app_selector(cr['spec'], app['uid'], comp_uid)
        if not applies:
            continue
        # Check if it intersects or is nearby
        applies = check_drone_area_selector(cr['spec'], app['drone_op_area'], True)
        if not applies:
            continue
        policy_copy = copy.deepcopy(cr['spec'])
        add_app_selector(policy_copy, app['uid'], comp_uid)
        uid = get_uuid()
        policy_copy['uid'] = uid
        policies.append(policy_copy)
    return policies


def get_privacy_control(app, comp_uid, node_name):
    """Retrieve PrivacyControl policies.

    Args:
        app (dict): The FluidityAppInfo dictionary.
        comp_uid (str): Component's unique identifier.
        node_name (str): The host node's name.

    Returns:
        list of dict: The list of related policies.
    """
    drones = get_custom_nodes('fluiditynodes', 'drone')
    node_spec = None
    node_type = 'drone'
    for node in drones:
        if node['metadata']['name'] == node_name:
            node_spec = node['spec']
    if node_spec is None:
        node_type = 'mobilenode'
        mobilenodes = get_custom_nodes('fluiditynodes', 'mobile')
        for node in mobilenodes:
            if node['metadata']['name'] == node_name:
                node_spec = node['spec']
        if node_spec is None:
            logger.error('Host node not found')
            return []
            
    cr_api = FluidityObjectsApi()
    try:
        crs = cr_api.list_fluidity_object('policies')
    except FluidityApiException:
        logger.error('Policies retrieval failed')
        return []

    policies = []
    for cr in crs['items']:
        if cr['spec']['policyType'] != 'privacyControl':
            continue
        if node_type == 'drone':
            applies = check_drone_selector(cr['spec'], node_spec)
        #else:
        #    applies = check_edgenode_selector(cr['spec'], node_spec)
        #if not applies:
        #    continue
        #applies = check_app_selector(cr['spec'], app['uid'], comp_uid)
        #if not applies:
        #    continue
        # Check if it intersects
        if node_type == 'drone':
            applies = check_drone_area_selector(cr['spec'], app['drone_op_area'])
        #else:
        #    applies = check_edge_area_selector(cr['spec'], node_spec['location'])
        #if not applies:
        #    continue
        policy_copy = copy.deepcopy(cr['spec'])
        add_app_selector(policy_copy, app['uid'], comp_uid)
        uid = get_uuid()
        policy_copy['uid'] = uid
        policies.append(policy_copy)
    return policies


def generate_policy_configs(comp_name, app):
    """Generate and send policy configurations for component instances
    accessing system services (drone/mobile and edge components).

    Args:
        comp_name (str): The component's name.
        app (dict): The FluidityAppInfo dictionary.
    """
    comp_spec = app['components'][comp_name]
    # logger.info('inside generate policy configs for comp: %s', comp_name)
    # logger.info('comp_spec[system_services] %s', comp_spec['systemServices'])
    if 'systemServices' in comp_spec:
        if 'mobility' in comp_spec['systemServices']:
            methods = comp_spec['systemServices']['mobility']['methods']
            # Single Pod/host
            host_node = comp_spec['hosts'][0]['name']
            host_address = get_node_internal_ip(host_node)
            # Unique identifier is the first (and only) pod name
            comp_uid = comp_spec['pod_names'][0]
            policy_cfg = []
            pol_ac = create_access_control('mobility', 'grant', methods, app['uid'], comp_uid)
            policy_cfg.append(pol_ac)
            pol_lc = get_limit_control(app, comp_uid, host_node)
            if pol_lc:
                policy_cfg.extend(pol_lc)
            pol_gc = get_geofence_control(app, comp_uid, host_node)
            if pol_gc:
                policy_cfg.extend(pol_gc)
            pol_gc = create_geofence_control(app, comp_spec)
            if pol_gc:
                policy_cfg.append(pol_gc)
            fpath = '{}/policy-config-mobility-{}.json'.format(app['fpath'], comp_uid)
            comp_spec['policy_cfg_mobility_fpath'] = fpath
            comp_spec['policy_cfg_mobility'] = {
                "policies_array": policy_cfg
            }
            with open(fpath, 'w') as json_f:
                json.dump(comp_spec['policy_cfg_mobility'], json_f, indent=4)
            # Send the policies to host node
            send_policy_config(host_address, POLICY_PORT_MOBILITY, fpath)

        if 'camera' in comp_spec['systemServices']:
            # List of dictionaries
            comp_spec['policy_cfg_camera'] = []
            #: List of str
            comp_spec['policy_cfg_camera_fpath'] = []
            methods = comp_spec['systemServices']['camera']['methods']
            # For each component instance
            logger.info('comp_spec[pod_manifests] %s', comp_spec['pod_manifests'])
            for manifest in comp_spec['pod_manifests']:
                logger.info('pod manifest %s', manifest)
                if manifest['status'] != 'PENDING':
                    continue
                policy_cfg = []
                # host_node = manifest['metadata']['name']
                host_node = manifest['file']['spec']['nodeName']
                host_address = get_node_internal_ip(host_node)
                logger.info('host node = %s' % host_node)
                logger.info('host addr = %s' % host_address)
                # Get unique identifier from the manifest
                comp_uid = manifest['file']['metadata']['name']
                pol_ac = create_access_control('camera', 'grant', methods, app['uid'], comp_uid)
                logger.info('after create access control')
                policy_cfg.append(pol_ac)
                pol_pc = get_privacy_control(app, comp_uid, host_node)
                if pol_pc:
                    policy_cfg.extend(pol_pc)
                fpath = '{}/policy-config-camera-{}.json'.format(app['fpath'], comp_uid)
                comp_spec['policy_cfg_camera_fpath'].append(fpath)
                policy_cfg_array = {
                    "policies_array": policy_cfg
                }
                comp_spec['policy_cfg_camera'].append(policy_cfg_array)
                with open(fpath, 'w') as json_f:
                    json.dump(policy_cfg_array, json_f, indent=4)
                # Send the policies to host node
                logger.info('going to send: %s, %s, %s',host_address, POLICY_PORT_CAMERA, fpath)
                send_policy_config(host_address, POLICY_PORT_CAMERA, fpath)


def generate_all_policy_configs(app):
    """Generate and send policy configurations for the components accessing
    system services (drone and edge components).

    Args:
        app (dict): The FluidityAppInfo dictionary.
    """
    logger.info('Generate policy configs for components of app: %s', app['name'])
    for comp_name in app['components']:
        comp_spec = app['components'][comp_name]
        if 'systemServices' in comp_spec:
            if 'mobility' in comp_spec['systemServices']:
                methods = comp_spec['systemServices']['mobility']['methods']
                # Single Pod/host
                host_node = comp_spec['hosts'][0]['name']
                host_address = get_node_internal_ip(host_node)
                # Unique identifier is the first (and only) pod name
                comp_uid = comp_spec['pod_names'][0]
                policy_cfg = []
                pol_ac = create_access_control('mobility', 'grant', methods, app['uid'], comp_uid)
                policy_cfg.append(pol_ac)
                pol_lc = get_limit_control(app, comp_uid, host_node)
                if pol_lc:
                    policy_cfg.extend(pol_lc)
                pol_gc = get_geofence_control(app, comp_uid, host_node)
                if pol_gc:
                    policy_cfg.extend(pol_gc)
                pol_gc = create_geofence_control(app, comp_spec)
                if pol_gc:
                    policy_cfg.append(pol_gc)
                fpath = '{}/policy-config-mobility-{}.json'.format(app['fpath'], comp_uid)
                comp_spec['policy_cfg_mobility_fpath'] = fpath
                comp_spec['policy_cfg_mobility'] = {
                    "policies_array": policy_cfg
                }
                with open(fpath, 'w') as json_f:
                    json.dump(comp_spec['policy_cfg_mobility'], json_f, indent=4)
                # Send the policies to host node
                # send_policy_config(host_address, POLICY_PORT_MOBILITY, fpath)

            if 'camera' in comp_spec['systemServices']:
                # List of dictionaries
                comp_spec['policy_cfg_camera'] = []
                #: List of str
                comp_spec['policy_cfg_camera_fpath'] = []
                methods = comp_spec['systemServices']['camera']['methods']
                # For each component instance
                for manifest in comp_spec['pod_manifests']:
                    policy_cfg = []
                    # host_node = manifest['metadata']['name']
                    host_node = manifest['file']['spec']['nodeName']
                    host_address = get_node_internal_ip(host_node)
                    # Get unique identifier from the manifest
                    comp_uid = manifest['file']['metadata']['name']
                    pol_ac = create_access_control('camera', 'grant', methods, app['uid'], comp_uid)
                    policy_cfg.append(pol_ac)
                    pol_pc = get_privacy_control(app, comp_uid, host_node)
                    if pol_pc:
                        policy_cfg.extend(pol_pc)
                    fpath = '{}/policy-config-camera-{}.json'.format(app['fpath'], comp_uid)
                    comp_spec['policy_cfg_camera_fpath'].append(fpath)
                    policy_cfg_array = {
                        "policies_array": policy_cfg
                    }
                    comp_spec['policy_cfg_camera'].append(policy_cfg_array)
                    with open(fpath, 'w') as json_f:
                        json.dump(policy_cfg_array, json_f, indent=4)
                    # Send the policies to host node
                    # send_policy_config(host_address, POLICY_PORT_CAMERA, fpath)


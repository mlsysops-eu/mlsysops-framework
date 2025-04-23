#/usr/bin/python3
"""Fluidity applications Controller."""
from __future__ import print_function
import argparse
import copy
import json
import socket
import logging
from threading import Semaphore
import os
import queue
import sys
import threading
import time
import importlib.util
from enum import Enum
#from profilehooks import profile
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from kubernetes.utils.quantity import parse_quantity
from ruamel.yaml import YAML
from mlstelemetry import MLSTelemetry
import asyncio 
from datetime import datetime
import inspect

# # Get the absolute path of the target directory
# module_dir = os.path.abspath("/home/runner")

# # Add it to sys.path
# sys.path.append(module_dir)

# Fluidity specific imports
# import redis_mgt as rm
from fluidity_crds_config import CRDS_INFO_LIST, API_GROUP
from fluidity_objects_api import FluidityObjectsApi, FluidityApiException
from fluidity_objects_util import dict2yaml, load_pod_file
from fluidity_nodes import get_drones, get_dronestations, get_edgenodes, get_mobilenodes, get_cloudnodes, get_k8s_nodes, get_custom_nodes, \
                                          set_fluiditynode_label, set_node_label, update_app_resources, set_node_annotation
from fluidityapp_candidates import find_candidates_drone, find_candidates_edge, find_candidates_hybrid, find_candidates_mobile
from fluidityapp_deploy import cleanup_pods, delete_running_pods, check_for_hosts_to_delete, create_adjusted_pods_and_configs, \
                                initiate_wifi_connection, destroy_wifi_connection, PROXY_MODE, create_svc, deploy_app_pods_and_configs, \
                                deploy_new_pods, send_notification_to_host, create_pod_object, extend_pod_label_template, \
                                extend_pod_env_template, create_svc_object, create_svc_manifest, create_pod_manifest, \
                                reconfigure_deployment
from fluidityapp_config import get_node_internal_ip, append_dict_to_list
from fluidityapp_monitor import FluidityAppMonitor
from fluidityapp_settings import RANGE_WIFI, RANGE_ZIGBEE, RANGE_BLUETOOTH, MOBILE_EDGE_PROXIMITY_RANGE
from fluidityapp_scheduler import select_hosts#, schedule_all_components
from fluidityapp_util import FluidityAppInfoDict, FluidityCompInfoDict, FluidityNodeInfoDict, HybridDroneInfoDict, HybridEdgeInfoDict, HybridMobileInfoDict
from geo_util import feature_to_shapely, coords_to_shapely, point_in_area
from operation_area import get_op_area_driver, get_op_area_passenger, get_op_area_edge, get_com_area_drone, get_com_area_edgenode
from fluidity_system_statistics import add_statistic_entry, add_migration_entry
import fluidityapp_settings as fluidityapp_settings

os.environ["LOCAL_OTEL_ENDPOINT"] = "http://10.64.83.176:9464/metrics"

mlsClient = MLSTelemetry("fluidity_mechanism", "fluidity_controller")
logger = logging.getLogger(__name__)

# OTEL Function to start the asyncio event loop in a separate thread

def start_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

async def log_listen():
    #logger.info('log_listen')
    await mlsClient.subscribeToLocalLogs(log_receive_handler_controller,"drone_controller")
# end OTEL 


#: System file directory of manifests
_MANIFESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../resources/manifests'))


info_vip = {
    'msg-type': 'vip-info',
    'comp-name': '',
    'vip': 'x.x.x.x'
}


class ExecMode(Enum):
    """Enumeration for execution modes."""
    DEV = 'DEV'
    DEPLOY = 'DEPLOY'
    EVAL = 'EVAL'
    TEST = 'TEST'


UI_TIMEOUT = 2
# codes for ui
IDLE = 0
PROCESSING_SUBMIT = 1
PROCESSING_REMOVE = 2
#COMPLETED = 1
# PROCESSING_SUBMIT = 2
# PROCESSING_REMOVE = 3
#ERROR = 4


async def send_model_submission_notification():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_ml_command', "gauge", PROCESSING_SUBMIT)
    await asyncio.sleep(UI_TIMEOUT)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_ml_command', "gauge", IDLE)

async def send_model_removal_notification():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_ml_command', "gauge", PROCESSING_REMOVE)
    await asyncio.sleep(UI_TIMEOUT)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_ml_command', "gauge", IDLE)

async def send_description_submission_notification():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_app_command', "gauge", PROCESSING_SUBMIT)
    await asyncio.sleep(UI_TIMEOUT)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_app_command', "gauge", IDLE)

async def send_description_removal_notification():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_app_command', "gauge", PROCESSING_REMOVE)
    await asyncio.sleep(UI_TIMEOUT)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_app_command', "gauge", IDLE)

def ensure_crds():
    """Ensure all Fluidity CRDs are registered.

    Checks if the Fluidity-related resource definitions are registered and
    registers any missing.
    """
    ext_api = client.ApiextensionsV1Api()
    # Get the list of registered CRD names
    current_crds = ext_api.list_custom_resource_definition().to_dict()['items']
    current_crds_names = [x['spec']['names']['singular'] for x in current_crds]

    for crd_info in CRDS_INFO_LIST:
        if crd_info['singular'] in current_crds_names:
            logger.info('Fluidity CRD: %s already exists', crd_info['kind'])
        else:
            logger.info('Creating Fluidity CRD: %s', crd_info['kind'])
            try:
                yaml = YAML(typ='safe')
                with open(crd_info['crd_file'], 'r') as data:
                    body = yaml.load(data)
            except IOError:
                logger.error('Resource definition not in dir %s.',
                             crd_info['crd_file'])
            try:
                ext_api.create_custom_resource_definition(body)
            except ApiException as exc:
                logger.exception('%s update failed: %s', crd_info['kind'], exc)
                # raise FluidityCrdsApiException from exc


class FluidityAppController():
    """Controller of FluidityApp objects."""

    def __init__(self, spade_pipe, exec_mode=ExecMode.TEST):
        self.exec_mode = exec_mode #: enum: The controller's execution mode
        #: dict: Registered Fluidity apps; key app name - value FluidityAppInfoDict dictionary
        self.apps_dict = {}
        self.nodes = copy.deepcopy(FluidityNodeInfoDict)
        #: dict: Key edgenode name - value dict with keys the intersection with all other nodes
        self.reachable_edgenodes = {}
        self.enable_statistics = False
        self.abort_event = threading.Event() #: Event for clean abort
        self.old_spec = None # For keeping the old app spec if operation:MODIFIED occurs
        self.notification_queue = queue.Queue() #: (internal) Application requests queue
        self.spade_pipe = spade_pipe
        #self.spade_server = SimpleServer(('localhost', 4554), SingleTCPHandler)
        self._app_handler_thr = None #: FluidityApp request handler thread
        self._app_monitor_thr_dict = {} # (1) Application monitor threads and (2) the required semaphores
        self.q_name = "endpoint_hash"
        # self.redis_hashmap = rm.RedisManager()
        # self.redis_hashmap.connect()

    def spade_recv_pipe(self):
        logger.info('Spade pipe recv started.')
        while True:
            logger.info('Going to block on pipe recv')
            message = self.spade_pipe.recv()
            logger.info('Received from spade msg: %s', message)
            event = message.get("event")  # Expected event field
            data = message.get("payload")  # Additional application-specific data
            if event is None or data is None:
                logger.error("[%s]: Event is None or data is None", inspect.currentframe().f_code.co_name)
                continue
            node = data.get("hostname")
            if node is None:
                logger.error("[%s]: node is None", inspect.currentframe().f_code.co_name)
                continue
            if event == 'COMPONENT_SPEC_UPDATE':
                logger.info('COMPONENT SPEC UPDATE EVENT')
                if name is None:
                    logger.error('[%s]: APP FIELD IS NONE.')
                elif name not in self.apps_dict:
                    logger.error('[%s]: APP %s IS NOT IN THE APP DICT.', inspect.currentframe().f_code.co_name, name)
                else:
                    self._handle_upd_app(name, self.apps_dict[name]['spec'], self.apps_dict[name]['uid'], data)
            elif event == 'POLICY_MODE_MODIFICATION':
                logger.info('POLICY_MODE_MODIFICATION EVENT')
                if new_policy is not None:
                    self._handle_policy_modification(name, self.apps_dict[name]['spec'], new_policy, self.apps_dict[name]['uid'])
                else:
                    logger.error('[%s]: NEW POLICY IS NONE.', inspect.currentframe().f_code.co_name)
            else:
                logger.error(f"Unhandled event type: {event}")

    def setup(self):
        """Initialize internal structures, setup k8s objects and start main
        control loop.

        Invokes :py:meth:`_setup_drones`, :py:meth:`_setup_edgenodes` and
        :py:meth:`control_loop`.

        NOTE: The lists keep cached data and should be retrieved/updated
        whenever a action to the respective objects is required.
        """
        
        # Clean-up old pods
        cleanup_pods()
        # Initialize infrastructure-related dicts
        self.nodes['k8snodes'] = get_k8s_nodes()
        self.nodes['edgenodes'] = get_custom_nodes('mlsysopsnodes', 'edge')
        self.nodes['mobilenodes'] = get_custom_nodes('mlsysopsnodes', 'mobile')
        self.nodes['cloudnodes'] = get_custom_nodes('mlsysopsnodes', 'cloud')
        fluidityapp_settings.init()
        # Update cached lists with the inserted labels/annotations
        self.nodes['k8snodes'] = get_k8s_nodes()
        self.nodes['edgenodes'] = get_custom_nodes('mlsysopsnodes', 'edge')
        self.nodes['mobilenodes'] = get_custom_nodes('mlsysopsnodes', 'mobile')
        self.nodes['cloudnodes'] = get_custom_nodes('mlsysopsnodes', 'cloud')
        logger.info('EdgeNodes Wireless range: %f', MOBILE_EDGE_PROXIMITY_RANGE)
        
        self._app_handler_thr = threading.Thread(name='app-request-handler', target=self._app_handler)
        self._app_handler_thr.setDaemon(True)
        self._app_handler_thr.start()

        # self._pipe_handler_thr = threading.Thread(name='spade-recv-msg-thread', target=self.spade_recv)
        # self._pipe_handler_thr.setDaemon(True)
        # self._pipe_handler_thr.start()
        if self.spade_pipe is not None:
            logger.info('Creating thread to communicate with SPADE agent via a pipe')
            self._spade_pipe_thr = threading.Thread(name='spade-recv-msg-thread', target=self.spade_recv_pipe)
            self._spade_pipe_thr.setDaemon(True)
            self._spade_pipe_thr.start()
        else:
            logger.info('Communication with spade is not enabled.')
        # Start main control loop
        self.control_loop()

    def _setup_drones(self):
        """Setup drone and dronestations-related resources.

        Adds and updates Fluidity-related fields, labels and annotations to
        drone (fluidity.gr/drone-station, fluidity.gr/direct-range)
        dronestation (drone names)
        and node k8s objects (fluidity.gr/node-type,fluidity.gr/node-spec,
        fluidity.gr/drone-station,fluidity.gr/direct-range).
        """
        for drone in self.nodes['drones']:
            # Find maximum direct communication range, if any
            # NOTE: In practice a single direct interface is supported per node
            max_net_range = 0
            net_range = 0
            for net_resource in drone['spec']['networkResources']:
                if net_resource['connectionType'] != 'direct':
                    continue
                if net_resource['interface'] == 'WiFi':
                    net_range = RANGE_WIFI
                elif net_resource['interface'] == 'ZigBee':
                    net_range = RANGE_ZIGBEE
                elif net_resource['interface'] == 'Bluetooth':
                    net_range = RANGE_BLUETOOTH
                if net_range > max_net_range:
                    max_net_range = net_range
            # Map drone to a station
            drone_loc = drone['spec']['location']
            point = coords_to_shapely(drone_loc[0], drone_loc[1])
            station_name = None
            for station in self.nodes['dronestations']:
                station_geom = feature_to_shapely(station['spec']['area'])
                is_inside =  point_in_area(point, station_geom)
                if not is_inside:
                    continue
                # Update dronestation fields (in list item and k8s CRD instance)
                # NOTE: Commented out for evaluation
                if 'droneNames' not in station['spec']:
                    station['spec']['droneNames'] = []
                # If drone already in station, ignore
                if drone['metadata']['name'] in station['spec']['droneNames']:
                    continue
                station['spec']['droneNames'].append(drone['metadata']['name'])
                station['spec']['droneNum'] += 1
                cr_api = FluidityObjectsApi()
                try:
                    cr_api.update_fluidity_object('dronestations',
                                                 station['metadata']['name'],
                                                 station)
                except FluidityApiException:
                    logger.error('Updating dronestation failed')
                # Update drone fields (in list item and k8s CRD instance)
                set_fluiditynode_label(drone['metadata']['name'],
                                'fluidity.gr/drone-station',
                                station['metadata']['name'])
                station_name = station['metadata']['name']
                # NOTE: Add separate labels to support multiple net technologies
                set_fluiditynode_label(drone['metadata']['name'],
                                'fluidity.gr/direct-range',
                                str(max_net_range))
                break
            # Map drone to k8s node
            # NOTE: Commented out this for the test/evaluation
            if self.exec_mode not in [ExecMode.TEST, ExecMode.EVAL]:
                for node in self.nodes['k8snodes']:
                    if node.metadata.name == drone['metadata']['name']:
                        set_node_label(node.metadata.name,
                                       'fluidity.gr/node-type',
                                       'drone')
                        set_node_annotation(node.metadata.name,
                                            'fluidity.gr/node-spec',
                                            json.dumps(drone['spec']))
                        # NOTE: Add separate labels to support multiple net technologies
                        set_node_label(node.metadata.name,
                                       'fluidity.gr/direct-range',
                                       str(max_net_range))
                        if station_name is None:
                            break
                        set_node_label(node.metadata.name,
                                       'fluidity.gr/drone-station',
                                       station_name)
                        break

    def _setup_edgenodes(self):
        """Setup edgenode-related resources.

        Adds and updates Fluidity-related labels and annotations to
        edgenode (fluidity.gr/direct-range)
        and node k8s objects (fluidity.gr/node-type,fluidity.gr/node-spec,
        fluidity.gr/direct-range).
        """
        for edgenode in self.nodes['edgenodes']:
            # Find direct communication ranges, if any
            # NOTE: In practice a single direct interface is supported per node
            max_net_range = 0
            net_range = 0
            for net_resource in edgenode['spec']['networkResources']:
                if net_resource['connectionType'] != 'direct':
                    continue
                if net_resource['interface'] == 'WiFi':
                    net_range = RANGE_WIFI
                elif net_resource['interface'] == 'ZigBee':
                    net_range = RANGE_ZIGBEE
                elif net_resource['interface'] == 'Bluetooth':
                    net_range = RANGE_BLUETOOTH
                if net_range > max_net_range:
                    max_net_range = net_range
            set_fluiditynode_label(edgenode['metadata']['name'],
                               'fluidity.gr/direct-range',
                               str(max_net_range))
             # NOTE: Commented out this for the test/evaluation
            if self.exec_mode not in [ExecMode.TEST, ExecMode.EVAL]:
                for node in self.nodes['k8snodes']:
                    if node.metadata.name == edgenode['metadata']['name']:
                        set_node_label(node.metadata.name,
                                       'fluidity.gr/node-type',
                                       'edgenode')
                        set_node_annotation(node.metadata.name,
                                            'fluidity.gr/node-spec',
                                            json.dumps(edgenode['spec']))
                        # NOTE: Add separate labels for different net technologies
                        set_node_label(node.metadata.name,
                                       'fluidity.gr/direct-range',
                                       str(max_net_range))

    def _set_edgenodes_reachability(self):
        """Get direct communication areas of nodes and their reachability
        from other nodes."""
        for edgenode in self.nodes['edgenodes']:
            edgenode_name = edgenode['metadata']['name']
            node_entry = {}
            node_entry['com_area'] = get_com_area_edgenode(edgenode)
            if node_entry['com_area'] is None:
                logger.info('Edgenode %s does not support direct com.', edgenode_name)
                continue
            # edgenode_com_area = get_com_area_edgenode(edgenode)
            for edgenode2 in self.nodes['edgenodes']:
                edgenode2_name = edgenode2['metadata']['name']
                node_entry[edgenode2_name] = {
                    'intersection': None,
                    'coverage': 0
                }
                if edgenode2_name == edgenode_name:
                    node_entry[edgenode2_name]['intersection'] = node_entry['com_area']
                    node_entry[edgenode2_name]['coverage'] = 1.0
                else:
                    edgenode2_com_area = get_com_area_edgenode(edgenode2)
                    # Discard node if it has not direct communication interface
                    if edgenode2_com_area is None:
                        continue
                    intersection = node_entry['com_area'].intersection(edgenode2_com_area)
                    node_entry[edgenode2_name]['intersection'] = intersection
                    node_entry[edgenode2_name]['coverage'] = intersection.area/node_entry['com_area'].area
            self.reachable_edgenodes[edgenode_name] = node_entry

    def _init_policy(self, app_name, policy_cfg, uid):
        # Read file containing the available policies and select one for the application.
        # Then make an entry for that application in this config for the app_handler to read
        # periodically. Then we can have other processes changing the desired policy at runtime.
        logger.info('Init policy for app %s and cfg file path %s', app_name, policy_cfg)
        body = None
        try:
            yaml = YAML(typ='safe')
            with open(policy_cfg, 'r') as data:
                body = yaml.load(data)
        except IOError as e:
            logger.error('Policy config not in path %s. error %s',policy_cfg, e)
        if body == None or 'availablePolicies' not in body:
            logger.error('No available policies found.')
            return None
        new_policy = None
        if uid != None:
            name_to_check = app_name.replace("-"+uid, '')
        else:
            name_to_check = app_name
        logger.info('name to check: %s', name_to_check)
        for policy in body['availablePolicies']:
            #logger.info(policy)
            if policy.startswith(name_to_check):
                new_policy = policy
                #logger.info('Found policy')
        if new_policy == None:
            logger.error('No available policies found.')
            return None

        if 'runningApps' not in body:
            body['runningApps'] = []
        new_entry = {
            'name': app_name,
            'currentPolicy': new_policy
        }
        body['runningApps'].append(new_entry)
        # TODO: Write updated body to config file so that the app_handler can check 
        # possible policy changes.
        return new_policy


    def _check_policy_updates(self, app_name, uid, curr_policy, policy_cfg):
        # Check if there is a new policy in the runningAps spec.
        # If yes, double-check that it exists in the availablePolicies.
        # If yes, change the policy. Otherwise, return error code.
        #logger.info('Init policy for app %s and cfg file path %s', app_name, policy_cfg)
        try:
            yaml = YAML(typ='safe')
            with open(policy_cfg, 'r') as data:
                body = yaml.load(data)
        except IOError:
            logger.error('Policy config not in path %s.',policy_cfg)
        if 'runningApps' not in body or 'availablePolicies' not in body:
            #logger.info('No runningApps and/or availablePolicies found.')
            return None
        for app in body['runningApps']:
            if 'name' not in app or 'currentPolicy' not in app:
                continue
            if app['name'] != app_name:
                continue
            if app['currentPolicy'] != self.apps_dict[app_name]['currentPolicy']:
                if uid != None:
                    name_to_check = app_name.replace("-"+uid, '')
                else:
                    name_to_check = app_name
                logger.info('name to check :%s', name_to_check)
                if app['currentPolicy'].startswith(name_to_check):
                    #logger.info('Found new policy %s for app %s.', app['currentPolicy'], app_name)
                    return app['currentPolicy']
                else: 
                    #logger.info('Failed to udpate policy. Policy %s does not start with the app name %s.', app['currentPolicy'], app_name)
                    return None
        #logger.error('No entry/currentPolicy found for this app.')
        return None

    def control_loop(self):
        """Main control loop of the FluidityApp contoller.

        Watches for fluidityapps resources and inserts them in the
        :py:attr:`~notification_queue`.
        """
        co_api = client.CustomObjectsApi()
        resource_v = ''
        while True:
            try:
                # Watch for fluidityapps resources
                # NOTE: Since the API watch may expire, catch exception and
                # change resource_version accordingly or set a timeout.
                # stream = watch.Watch().stream(
                #     co_api.list_cluster_custom_object, API_GROUP, 'v1',
                #     'fluidityapps', resource_version='')
                stream = watch.Watch().stream(
                    co_api.list_cluster_custom_object, API_GROUP, 'v1',
                    'mlsysopsapps', resource_version=resource_v,
                    timeout_seconds = 86400)
                for event in stream:
                    #fluidityapp_settings.control_loop_start = time.perf_counter()
                    operation = event['type']
                    obj = event['object']
                    # policy_update = obj.get('currentPolicy')
                    #logger.info(obj)
                    # logger.info('policy: %s', policy_update)
                    # app_spec = obj.get('spec')
                    # if not app_spec:
                    #     logger.info('No info found. Continue')
                    #     continue
                    metadata = obj.get('metadata')
                    app_name = metadata['name']
                    app_uid = metadata['uid']
                    logger.info('Handling %s on %s', operation, app_name)
                    logger.info('uid %s', app_uid)
                    if 'uth-demo-app' in app_name:
                        if operation == 'ADDED':
                            asyncio.run(send_description_submission_notification())
                        elif operation == 'DELETED':
                            asyncio.run(send_description_removal_notification())
                    elif 'node-model-app' in app_name:
                        if operation == 'ADDED':
                            asyncio.run(send_model_submission_notification())
                        elif operation == 'DELETED':
                            asyncio.run(send_model_removal_notification())
                    if app_name not in self.apps_dict:
                        logger.info('New app: %s - not in apps_dict', app_name)
                    app_req = {
                        'type': 'app-desc',
                        'operation': operation,
                        'name': app_name,
                        #'updatedPolicy': policy_update,
                        #'spec': app_spec,
                        'spec': obj,
                        'uid': app_uid
                    }
                    self.notification_queue.put(app_req)
            except KeyboardInterrupt:
                self.abort_event.set()
                break
            except ApiException as exc:
                logger.error('API exception in watching FluidityApps objects: %s', exc)


    def _app_handler(self):
        """FluidityApp handler thread.

        Receives application deployment requests through the
        :py:attr:`~notification_queue` and serves them one at a time by invoking
        the respective handling method. It exits in case the abort event is set.
        """
        logger.info('AppHandler thread started')
        while True:
            try:
                # Wake periodically just to check if abort event is set to exit
                req = self.notification_queue.get(timeout=1)
                if self.abort_event.is_set():
                    break
                if req['operation'] == 'ADDED':
                    self._handle_add_app(req['name'], req['spec'], req['uid'])
                elif req['operation'] == 'MODIFIED':
                    # If the notify function triggered adaptation or the app description has been modified
                    if req['type'] == 'resource-update' or req['type'] == 'app-desc':
                        if req['name'] in self.apps_dict:
                            self._handle_upd_app(req['name'], self.apps_dict[req['name']]['spec'], self.apps_dict[req['name']]['uid'])
                elif req['operation'] == 'DELETED':
                    self._handle_rm_app(req['name'], req['spec'], req['uid'])
            except queue.Empty:
                # Check if policy has changed for the available applications.
                # If yes, update it using the handle_policy_modification function.
                # Read file and iterate over the available policies.
                for app_name in self.apps_dict:
                    #logger.info('Checking app with name: %s', app_name)
                    new_policy = self._check_policy_updates(app_name, self.apps_dict[app_name]['internal_uid'], self.apps_dict[app_name]['currentPolicy'], fluidityapp_settings.policy_config_file)
                    if not new_policy:
                        continue
                    logger.info('Found policy update for app %s. New policy is %s.', app_name, new_policy)
                    self._handle_policy_modification(app_name, self.apps_dict[app_name]['spec'], new_policy, self.apps_dict[app_name]['uid'])

    def _handle_policy_modification(self, app_name, app_spec, policy_name, app_uid, ):
        self._app_monitor_thr_dict[app_name]['block_monitor_sem'].acquire()
        self._app_monitor_thr_dict[app_name]['block_resource_checker_sem'].acquire()
        
        self.apps_dict[app_name]['currentPolicy'] = policy_name
        #policy_name = updated_policy[0]['name']
        logger.info('policy_name : %s', policy_name)
        if policy_name == 'fluidityplugin_new_policy.py':
            logger.info('Going to enable statistics.')
            self.enable_statistics = True
        else:
            logger.info('Statistics are not enabled.')
        
        try:
            policy_path = fluidityapp_settings.policy_dir+self.apps_dict[app_name]['currentPolicy']
            logger.info('Policy fpath: %s', policy_path)
            spec = importlib.util.spec_from_file_location(policy_name, policy_path)
            policy_plugin = importlib.util.module_from_spec(spec)
            sys.modules[policy_name] = policy_plugin
            spec.loader.exec_module(policy_plugin)
            self.apps_dict[app_name]['plugin_policy'] = policy_plugin
        except Exception as e:
            logger.error('Failed to load policy. Caught exc %s', e)
            return
        logger.info('Policy plugin %s', self.apps_dict[app_name]['plugin_policy'])
        self._app_monitor_thr_dict[app_name]['block_monitor_sem'].release()
        self._app_monitor_thr_dict[app_name]['block_resource_checker_sem'].release()

    def _handle_add_app(self, app_name, app_spec, app_uid):
        """Handle the deployment request of a new application.

        Args:
            app_name (str): The name of the application.
            app_spec (dict): The specification of the application.
            app_uid (str): The unique identifier of the application.
        """
        # logger.info('Add FluidityApp %s\nuid: %s\nspec: %s',
        #             app_name, app_uid, app_spec)
        app_dict = copy.deepcopy(FluidityAppInfoDict)
        app_dict['name'] = app_name
        app_dict['uid'] = app_uid
        app_dict['spec'] = app_spec
        if 'mlsysops-id' in app_spec:
            app_dict['internal_uid'] = app_spec['mlsysops-id']
        else:
            app_dict['internal_uid'] = None
        app_dict['currentPolicy'] = self._init_policy(app_name, fluidityapp_settings.policy_config_file, app_dict['internal_uid'])
        # logger.info(app_dict['name'])
        # logger.info(app_dict['uid'])
        # logger.info(app_dict['spec'])
        if app_dict['currentPolicy'] == None:
            logger.error('Policy selection failed for app %s, the policy must start with the app_name.', app_name)
            return
        app_dict['reachable_edgenodes'] = self.reachable_edgenodes
        logger.info('app_dict[currentPolicy] : %s', app_dict['currentPolicy'])
        if app_dict['currentPolicy'] == 'fluidityplugin_new_policy.py':
            logger.info('Going to enable statistics.')
            self.enable_statistics = True
        else:
            logger.info('Statistics are not enabled.')
        try:
            policy_path = fluidityapp_settings.policy_dir+app_dict['currentPolicy']
            logger.info('Policy fpath: %s', policy_path)
            logger.info(app_dict['currentPolicy'])
            spec = importlib.util.spec_from_file_location(app_dict['currentPolicy'], policy_path)
            logger.info(spec)
            policy_plugin = importlib.util.module_from_spec(spec)
            sys.modules[app_dict['currentPolicy']] = policy_plugin
            spec.loader.exec_module(policy_plugin)
            app_dict['plugin_policy'] = policy_plugin
        except Exception as e:
            logger.error('Failed to load policy. Caught exc %s', e)
            return
        logger.info('Policy configured successfully.')
        logger.info('Cluster id: %s', fluidityapp_settings.cluster_id)
        
        tmp_cluster_id = None
        if 'clusterPlacement' in app_spec:
            logger.info('Parsing clusterPlacement')
            if 'clusterID' in app_spec['clusterPlacement']:
                # Selecting the first cluster
                tmp_cluster_id = app_spec['clusterPlacement']['clusterID'][0]
            else:
                logger.error('No clusterID found in app description.')
        logger.info('App %s has required clusterID set to: %s', app_name, tmp_cluster_id)
        # Iterate over components and populate the various data structures
        for component in app_spec['components']:
            #: dict: Extended component spec, with FluidityCompInfoDict fields
            comp_spec = copy.deepcopy(FluidityCompInfoDict)
            comp_spec['spec'] = copy.deepcopy(component)
            comp_spec['name'] = component['Component']['name']
            if 'externalAccess' in component:
                comp_spec['external_access'] = component['externalAccess']
            else:
                comp_spec['external_access'] = False
            # logger.info('comp_spec %s', comp_spec)
            # logger.info('comp_spec[spec] %s', comp_spec['spec'])
            if 'uid' in component['Component']:
                #logger.info('Component uid %s', component['Component']['uid'])
                comp_spec['uid'] = component['Component']['uid']
            if tmp_cluster_id != None:
                comp_spec['cluster_id'] = tmp_cluster_id
            #logger.info('name: %s, cluster_id: %s', comp_spec['name'], comp_spec['cluster_id'])
            # Add component to curr_deployment internal structure
            app_dict['curr_plan']['curr_deployment'][comp_spec['name']] = []
            # Update the way that this template is created (without reading a file)
            comp_spec['pod_template'] = create_pod_manifest(app_name, app_uid, comp_spec)
            # logger.info("*******")
            # logger.info(component)
            comp_spec['placement'] = None
            if 'nodePlacement' in component:
                if 'labels' in component['nodePlacement']:
                    comp_spec['labels'] = component['nodePlacement']['labels']
                    #logger.info('Added labels %s', comp_spec['labels'])
                if 'mobility' in component['nodePlacement']:
                    app_dict['mobile_comp_names'].append(comp_spec['name'])
                    app_dict['mobile_comp_specs'].append(comp_spec)
                    comp_spec['placement'] = 'mobile'
                elif 'continuumLayer' in component['nodePlacement']:
                    if len(component['nodePlacement']['continuumLayer']) > 1 or component['nodePlacement']['continuumLayer'][0] == '*':
                        app_dict['hybrid_comp_names'].append(comp_spec['name'])
                        app_dict['hybrid_comp_specs'].append(comp_spec)
                        comp_spec['placement'] = 'hybrid'
                    elif component['nodePlacement']['continuumLayer'][0] == 'Edge':
                        app_dict['edge_comp_names'].append(comp_spec['name'])
                        app_dict['edge_comp_specs'].append(comp_spec)
                        comp_spec['placement'] = 'edge'
                    elif component['nodePlacement']['continuumLayer'][0] == 'EdgeInfrastructure':
                        app_dict['edge_infra_comp_names'].append(comp_spec['name'])
                        app_dict['edge_infra_comp_specs'].append(comp_spec)
                        comp_spec['placement'] = 'edge_infra'
                    elif component['nodePlacement']['continuumLayer'][0] == 'FarEdge':
                        app_dict['far_edge_comp_names'].append(comp_spec['name'])
                        app_dict['far_edge_comp_specs'].append(comp_spec)
                        comp_spec['placement'] = 'far_edge'
                    elif component['nodePlacement']['continuumLayer'][0] == 'Cloud':
                        app_dict['cloud_comp_names'].append(comp_spec['name'])
                        app_dict['cloud_comp_specs'].append(comp_spec)
                        comp_spec['placement'] = 'cloud'             
            logger.info('placement: %s', comp_spec['placement'])
            if 'QoS-Metrics' in component:
                comp_spec['qos_metrics'] = component['QoS-Metrics']
                logger.info('Comp has QoS requirements %s', comp_spec['qos_metrics'])
            # Retrieve computing resource requests/limits for Pod containers
            pod_spec = comp_spec['pod_template']['spec']
            #logger.info('Pod spec: %s', pod_spec)
            for container in pod_spec['containers']:
                if 'resources' not in container:
                    continue
                if 'requests' in container['resources']:
                    request = container['resources']['requests']
                    cpu = float(parse_quantity(request['cpu']))
                    memory = float(parse_quantity(request['memory']))
                    comp_spec['resources_requests']['cpu'] += cpu
                    comp_spec['resources_requests']['memory'] += memory
                if 'limits' in container['resources']:
                    limit = container['resources']['limits']
                    cpu = float(parse_quantity(limit['cpu']))
                    memory = float(parse_quantity(limit['memory']))
                    comp_spec['resources_limits']['cpu'] += cpu
                    comp_spec['resources_limits']['memory'] += memory
            # If limits < requests, limits = requests
            if comp_spec['resources_limits']['cpu'] < comp_spec['resources_requests']['cpu']:
                comp_spec['resources_limits']['cpu'] = comp_spec['resources_requests']['cpu']
            if comp_spec['resources_limits']['memory'] < comp_spec['resources_requests']['memory']:
                comp_spec['resources_limits']['memory'] = comp_spec['resources_requests']['memory']
            # Add component specification to 'components' dict for fast lookups
            app_dict['components'][comp_spec['name']] = comp_spec

        # Get I/O component relations and create service manifests/objects
        app_dict['state'] = 'COMPONENTS_IO_RELATIONS'
        print("IO Relations")
        for comp_name in app_dict['components']:
            comp_spec = app_dict['components'][comp_name]
            # Create Service manifest (dict) for service-providing components
            pod_template = comp_spec['pod_template']
            proto = None
            ports = None
            for container in pod_template['spec']['containers']:
                if 'ports' not in container:
                    continue
                ports = container['ports']
                for port in ports:
                    svc_port = port['containerPort']
                    if 'protocol' in port:
                        proto = port['protocol']
                        logger.info('Desired protocol %s', proto)  
                    # NOTE: We assume a single exposed service port
                    break
                # NOTE: We assume single-container Pods
                break
            if ports != None:
                svc = create_svc_manifest(app_name, app_uid, comp_name, svc_port, proto, comp_spec['external_access'])
                obj = create_svc_object(app_name, app_uid, comp_name, svc_port, proto, comp_spec['external_access'])
                #fpath = '{}/svc-{}.yaml'.format(app_fpath, comp_name)
                comp_spec['svc_manifest'] = svc
                comp_spec['svc_object'] = obj
                #comp_spec['svc_fpath'] = fpath
                comp_spec['svc_port'] = svc_port
                # Create manifest file - Just for visual debugging
                #dict2yaml(comp_spec['svc_manifest'], comp_spec['svc_fpath'])
                # res = apply_manifest_file(comp_spec['svc_fpath'])
                # if res is None:
                #     return
                # # Retrieve the created 'V1Service' object and its assigned VIP
                # svc_obj = res[0][0]
                # comp_spec['svc_vip'] = svc_obj.spec.cluster_ip
                svc_obj = create_svc(comp_spec['svc_manifest'])
                if svc_obj is None:
                    logger.error('Failed to create svc with manifest %s', comp_spec['svc_manifest'])
                    return
                # Retrieve the assigned VIP
                logger.info(comp_name)
                logger.info(svc_obj.spec.cluster_ip)
                #logger.info(svc_obj.spec.ports[0].nodePort)
                comp_spec['local_endpoint'] = svc_obj.spec.cluster_ip+':'+str(svc_obj.spec.ports[0].port)
                if svc_obj.spec.ports[0].node_port:
                    # The node IP will be at a later stage.
                    comp_spec['global_endpoint'] = str(svc_obj.spec.ports[0].node_port)
                else:
                    comp_spec['global_endpoint'] = None
                #print(svc_obj.spec)
                comp_spec['svc_vip'] = svc_obj.spec.cluster_ip

        # Extend component Pod template manifests/objects with Fluidity-related info
        app_dict['state'] = 'COMPONENTS_POD_TEMPLATES_CREATION'
        if 'componentInteractions' in app_spec:
            for interaction in app_spec['componentInteractions']:
                logger.info('Comp interactions %s', interaction)
                ingress_comp = None
                egress_comp = None
                if interaction['type'] == 'egress':
                    ingress_comp = interaction['componentName1']
                    egress_comp = interaction['componentName2']
                else:
                    ingress_comp = interaction['componentName2']
                    egress_comp = interaction['componentName1']
                if egress_comp is not None and ingress_comp is not None:
                    egress_spec = app_dict['components'][egress_comp]
                    comp_spec = app_dict['components'][ingress_comp]
                    #logger.info('Ingress comp spec : %s', comp_spec)
                    #logger.info('Egress comp spec : %s', egress_spec)
                    svc_addr = '{}:{}'.format(egress_spec['svc_vip'], egress_spec['svc_port'])
                    # Add service VIP:port as parameter to container
                    #print(comp_name)
                    #print(svc_addr)
                    extend_pod_env_template(comp_spec['pod_template'], svc_addr)
        for comp_name in app_dict['components']:
            comp_spec = app_dict['components'][comp_name]
            extend_pod_label_template(comp_spec['pod_template'], app_name,
                                    app_uid, comp_name, comp_spec['placement'])
            #logger.info('pod manifest %s', comp_spec['pod_template'])
            comp_spec['pod_object'] = create_pod_object(comp_spec['pod_template'])
        # Add new app to apps dictionary
        self.apps_dict[app_name] = app_dict
        #logger.info(self.apps_dict[app_name])
        app_dict['state'] = 'HOSTS_SELECTION'
        while True:
            # Store the policy inside the app-related structure and also pass the module to the Monitor.
            initial_deployment, self.apps_dict[app_name]['context'] = self.apps_dict[app_name]['plugin_policy'].initial_plan({'name':app_name,'spec':self.apps_dict[app_name]['spec']}, dict(self.nodes))
            if not initial_deployment:
                logger.info('Host selection failed. Trying again in 10 seconds.')
                time.sleep(10)
                self.nodes['k8snodes'] = get_k8s_nodes()
                # NOTE: Here we will use the official MLSysOps descriptions
                self.nodes['edgenodes'] = get_custom_nodes('mlsysopsnodes', 'edge')
                self.nodes['mobilenodes'] = get_custom_nodes('mlsysopsnodes', 'mobile')
                self.nodes['cloudnodes'] = get_custom_nodes('mlsysopsnodes', 'cloud')
            else:
                logger.info('Initial deployment: %s' % initial_deployment)
                break
        #print(self.apps_dict)
        #Translation of the initial_plan()s output
        for comp_name in initial_deployment:
            logger.info('Initial deployment %s' % comp_name)
            comp_spec = self.apps_dict[app_name]['components'][comp_name]
            host_name = initial_deployment[comp_name][0]['name']
            logger.info('Initial host %s' % host_name)
            if 'internal_uid' in app_dict and app_dict['internal_uid'] != None:
                timestamp = datetime.now()
                info = {
                    'status': 'pending',
                    'timestamp': str(timestamp)
                }
                logger.info('Going to push to redis endpoint_queue the value %s', info)
                # info_bytes = pickle.dumps(info)
                # self.redis_hashmap.update_dict_value('endpoint_hash', app_dict['internal_uid'], str(info))
                #self.redis_hashmap.update_dict_value('my_dictionary' ,comp_name, 'pending')
            for node in self.nodes['cloudnodes']:
                if node['metadata']['name'] == host_name:
                    app_dict['cloud_comp_names'].append(comp_spec['name'])
                    app_dict['cloud_comp_specs'].append(comp_spec)
                    comp_spec['placement'] = 'cloud'
                    break
            #logger.info(self.nodes['edgenodes'])
            for node in self.nodes['edgenodes']:
                if node['metadata']['name'] == host_name:
                    app_dict['edge_comp_names'].append(comp_spec['name'])
                    app_dict['edge_comp_specs'].append(comp_spec)
                    comp_spec['placement'] = 'edge'
                    #logger.info('comp spec: %s', comp_spec)
                    break
            for node in self.nodes['mobilenodes']:
                if node['metadata']['name'] == host_name:
                    app_dict['mobile_comp_names'].append(comp_spec['name'])
                    app_dict['mobile_comp_specs'].append(comp_spec)
                    comp_spec['placement'] = 'mobile'
                    break
            for node in self.nodes['cloudnodes']:
                if node['metadata']['name'] == host_name:
                    app_dict['cloud_comp_names'].append(comp_spec['name'])
                    app_dict['cloud_comp_specs'].append(comp_spec)
                    comp_spec['placement'] = 'cloud'
                    break
            if comp_name in self.apps_dict[app_name]['hybrid_mobile_comp_names']:
                # Check if a cloud node will host the hybrid component.
                for node in self.nodes['cloudnodes']:
                    if node['metadata']['name'] == host_name:
                        comp_spec['host_hybrid_cloud'] = host_name
                        #logger.info(comp_spec['host_hybrid_cloud'])
                        break

        self.apps_dict[app_name]['curr_plan']['curr_deployment'] = dict(initial_deployment)
        app_dict['state'] = 'APP_DEPLOYMENT'
        hosts_found, agent_msg = deploy_app_pods_and_configs(app_dict, self.apps_dict[app_name]['curr_plan']['curr_deployment'])
        if not hosts_found:
            logger.error('Initial deployment failed. No hosts found.')
            return   
        if agent_msg != [] and self.spade_pipe is not None:
            logger.info('Going to push %s to agent queue.', agent_msg)
            self.spade_pipe.send(agent_msg)
            #spade_send_msg(agent_msg)
            #spade_write_file(agent_msg)
        for comp_name in initial_deployment:
            if 'internal_uid' not in app_dict or app_dict['internal_uid'] == None:
                continue
            node_ip = None
            host = initial_deployment[comp_name][0]['name']
            logger.info('HOST %s', host)
            comp_spec = self.apps_dict[app_name]['components'][comp_name]
            for node in self.nodes['k8snodes']:
                node_name = node.metadata.name
                logger.info(node_name)
                if node.metadata.name == host:
                    internal_ip = None
                    external_ip = None
                    addresses = node.status.addresses
                    logger.info('Addresses %s',addresses)
                    for address in addresses:
                        if address.type == "ExternalIP":
                            external_ip = address.address
                            logger.info(f"Node: {node_name}, External IP: {external_ip}")
                        elif address.type == "InternalIP":
                            internal_ip = address.address
                            logger.info(f"Node: {node_name}, Internal IP: {internal_ip}") 
                    if external_ip == None:
                        logger.info('External IP not found for node that should be accessible externally.')
                        if internal_ip == None:
                            logger.info('Internal IP not found for node that should be accessible externally.')
                        else:
                            node_ip = internal_ip
                    else:
                        node_ip = external_ip
                    break
            timestamp = datetime.now()
            info = {
                'status': 'deployed',
                'timestamp': str(timestamp),
                'local_endpoint': comp_spec['local_endpoint']
            }
            if comp_spec['global_endpoint'] and node_ip:
                info['global_endpoint'] = node_ip+':'+comp_spec['global_endpoint']
            logger.info('Going to push to redis endpoint_queue the value %s', info)
            # self.redis_hashmap.update_dict_value('endpoint_hash', app_dict['internal_uid'], str(info))
            #self.redis_hashmap.update_dict_value('my_dictionary', comp_name, 'deployed')
            # self.redis_hashmap.push(self.q_name, info)
        app_dict['state'] = 'APP_EXECUTION'
        # Create fluidityapp monitor thread and insert it to the list
        # thr_name = '{}-{}'.format('app-monitor', app_name)
        block_monitor_sem = Semaphore(1)
        block_resource_checker_sem = Semaphore(1)
        system_metrics = {
            'statistics': {}
        }
        for entry in self.nodes['edgenodes']:
            name = entry['metadata']['name']
            add_statistic_entry(system_metrics, name)
            for tmp_entry in self.nodes['edgenodes']:
                tmp_name = tmp_entry['metadata']['name']
                if name != tmp_name:
                    add_migration_entry(system_metrics, name, tmp_name)
            for tmp_entry in self.nodes['cloudnodes']:
                tmp_name = tmp_entry['metadata']['name']
                add_migration_entry(system_metrics, name, tmp_name)
            for tmp_entry in self.nodes['mobilenodes']:
                tmp_name = tmp_entry['metadata']['name']
                add_migration_entry(system_metrics, name, tmp_name)
        for entry in self.nodes['mobilenodes']:
            name = entry['metadata']['name']
            add_statistic_entry(system_metrics, name)
            for tmp_entry in self.nodes['mobilenodes']:
                tmp_name = tmp_entry['metadata']['name']
                if name != tmp_name:
                    add_migration_entry(system_metrics, name, tmp_name)
            for tmp_entry in self.nodes['edgenodes']:
                tmp_name = tmp_entry['metadata']['name']
                add_migration_entry(system_metrics, name, tmp_name)
            for tmp_entry in self.nodes['cloudnodes']:
                tmp_name = tmp_entry['metadata']['name']
                add_migration_entry(system_metrics, name, tmp_name)
        for entry in self.nodes['cloudnodes']:
            name = entry['metadata']['name']
            add_statistic_entry(system_metrics, name)
            for tmp_entry in self.nodes['cloudnodes']:
                tmp_name = tmp_entry['metadata']['name']
                if name != tmp_name:
                    add_migration_entry(system_metrics, name, tmp_name)
            for tmp_entry in self.nodes['edgenodes']:
                tmp_name = tmp_entry['metadata']['name']
                add_migration_entry(system_metrics, name, tmp_name)
            for tmp_entry in self.nodes['mobilenodes']:
                tmp_name = tmp_entry['metadata']['name']
                add_migration_entry(system_metrics, name, tmp_name)
        #logger.info('system_metrics structure: %s' % system_metrics)
        app_monitor_thr = FluidityAppMonitor(self.apps_dict[app_name], block_resource_checker_sem,
                                            block_monitor_sem, self.nodes,
                                            self.notification_queue, self.apps_dict[app_name]['context'], system_metrics)
        tmp_dict = {
            'thread': app_monitor_thr,
            'block_monitor_sem': block_monitor_sem,
            'block_resource_checker_sem': block_resource_checker_sem,
            'system_metrics': system_metrics
        }
        self._app_monitor_thr_dict[app_name] = tmp_dict
        app_monitor_thr.start()
        ### UI update send idle state
        fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_app_command', "gauge", IDLE)
        fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_ml_command', "gauge", IDLE)

    def _handle_upd_app(self, app_name, new_app_spec, app_uid, spade_request=None):
        """Handle the update request for an existing application .

        Args:
            app_name (str): The name of the application.
            new_app_spec (dict): The (possibly) new specification of the application.
            app_uid (str): The app uid for app management within Fluidity.
            spade_request (list): List of updated Pod specs sent by an MLSysOps agent.
        """
        #fluidityapp_settings.timer_start = time.perf_counter()
        # Notify monitor to stop checking
        logger.info('handle_upd_add, before sem acquisition')
        self._app_monitor_thr_dict[app_name]['block_monitor_sem'].acquire()
        self._app_monitor_thr_dict[app_name]['block_resource_checker_sem'].acquire()
        logger.info('handle_upd_add, before sem acquisition')
        # We just check for spade reconfiguration requests, mainly update Pod specs (deploy new pod+remove old pod)
        # NOTE: We need to see the sequence of removal/deployment
        if spade_request is not None:
            logger.info('Received reconfiguration request %s', spade_request)
            # logic to handle the request
            result = reconfigure_deployment(self.apps_dict[app_name], spade_request)
            if result:
                logger.info('Modified Pod specs accordingly.')
            else:
                logger.error('Pod spec modification failed')
            self._app_monitor_thr_dict[app_name]['block_monitor_sem'].release()
            self._app_monitor_thr_dict[app_name]['block_resource_checker_sem'].release()
            return
        # Hold the starting time of adaptation in order to calc the adaptation delay sent to the context
        total_adaptation_start = time.perf_counter()
        # NOTE: Check if self.nodes could be removed from the parameters.
        new_deployment_plan, self.apps_dict[app_name]['context'] = self.apps_dict[app_name]['plugin_policy'].re_plan(
                                                                        self.apps_dict[app_name]['spec'],
                                                                        new_app_spec,
                                                                        self.apps_dict[app_name]['context'],
                                                                        self.apps_dict[app_name]['curr_plan']['curr_deployment'])
        
        
        # NOTE: This is needed only for pod cleaning reasons
        if not new_deployment_plan:
            logger.error('Caught empty deployment plan. Going to clean the pods.')
            # Cleanup INACTIVE hosts and pods, if any.
            ret, agent_msg = check_for_hosts_to_delete(self.apps_dict[app_name], self.nodes['edgenodes'])
            if not ret:
                logger.error('check_for_hosts_to_delete failed.')
            if agent_msg != [] and self.spade_pipe is not None:
                logger.info('Going to push %s to agent queue.', agent_msg)
                self.spade_pipe.send(agent_msg)
                #spade_send_msg(agent_msg)
                #spade_write_file(agent_msg)
            self._app_monitor_thr_dict[app_name]['block_monitor_sem'].release()
            self._app_monitor_thr_dict[app_name]['block_resource_checker_sem'].release()
            logger.info('Host selection failed. Going to return.')
            return
        # Update the app_spec and the deployment plan
        self.apps_dict[app_name]['spec'] = new_app_spec
        #self.apps_dict[app_name]['curr_plan'] = new_deployment_plan
        
        for comp_name in new_deployment_plan['curr_deployment']:
            comp_spec = self.apps_dict[app_name]['components'][comp_name]
            action = new_deployment_plan['curr_deployment'][comp_name]['action']
            # For deploy or remove actions.
            host = None
            # For move action.
            move_src_host = None
            move_target_host = None
            if action == 'move':
                move_src_host = new_deployment_plan['curr_deployment'][comp_name]['src_host']
                move_target_host = new_deployment_plan['curr_deployment'][comp_name]['target_host']
                append_dict_to_list({'name': move_src_host, 'status': 'INACTIVE'}, comp_spec['hosts'])
                append_dict_to_list({'name': move_target_host, 'status': 'PENDING'}, comp_spec['hosts'])
            elif action == 'deploy' or action == 'remove':
                host = new_deployment_plan['curr_deployment'][comp_name]['host']
                status = 'INACTIVE'
                if action == 'deploy':
                    status = 'PENDING'
                append_dict_to_list({'name': host, 'status': status}, comp_spec['hosts'])
                logger.info(comp_spec['hosts'])
            else:
                logger.error('Policy provided invalid action. Going to return.')
                self._app_monitor_thr_dict[app_name]['block_monitor_sem'].release()
                self._app_monitor_thr_dict[app_name]['block_resource_checker_sem'].release()
                return
            self.apps_dict[app_name]['curr_plan']['curr_deployment'][comp_name] = list(comp_spec['hosts'])


            if comp_name not in self.apps_dict[app_name]['hybrid_mobile_comp_names']:
                continue
            # Check if a cloud node will host the hybrid component.
            # If the move target host is a cloud node or the deploy host is a cloud node we set the new host.
            # Else we reset it to None.
            comp_spec['host_hybrid_cloud'] = None
            for node in self.nodes['cloudnodes']:
                if node['metadata']['name'] == move_target_host:
                    comp_spec['host_hybrid_cloud'] = move_target_host
                    break
                elif node['metadata']['name'] == host and action == 'deploy':
                    comp_spec['host_hybrid_cloud'] = host
                    break
        
        if self.enable_statistics:
            # Find the src_name, dst_name for the ImageChecker component
            src_name = None
            dst_name = None
            for entry_name in new_deployment_plan['curr_deployment']:
                if entry_name != 'new-image-checker':
                    continue
                # TODO: Check this structure
                for host in new_deployment_plan['curr_deployment'][entry_name]:
                    if host['status'] == 'PENDING':
                        dst_name = host['name']
                    elif host['status'] == 'INACTIVE':
                        src_name = host['name']
        

        if 'enable_redirection' in new_deployment_plan and new_deployment_plan['enable_redirection'] == True:
            # Start a new thread, dedicated to initiate the WiFi connection between the mobile node and the edge node.
            # We give a copy of the structure because of concurrency. This thread will only read these structures and 
            # does not need to ensure they are coherent with the data that the Controller updates/parses at runtime.
            self._init_connection_thr = threading.Thread(name='connection-init',
                                                        target=initiate_wifi_connection,
                                                        args=(self.apps_dict[app_name],
                                                        self.apps_dict[app_name]['hybrid_mobile_comp_names'][0],
                                                        self.nodes['edgenodes']))
            self._init_connection_thr.start()
        if 'disable_redirection' in new_deployment_plan and new_deployment_plan['disable_redirection'] == True:
            self._destroy_connection_thr = threading.Thread(name='connection-destroy',
                                                        target=destroy_wifi_connection,
                                                        args=(self.apps_dict[app_name],
                                                        self.apps_dict[app_name]['hybrid_mobile_comp_names'][0],
                                                        self.nodes['edgenodes']))
            self._destroy_connection_thr.start()
            logger.info('connection-destroy Thread created. %s' % self._destroy_connection_thr)
        # Create adjusted pod manifests
        create_adjusted_pods_and_configs(self.apps_dict[app_name])
        # Deploy new Pods
        agent_msg = deploy_new_pods(self.apps_dict[app_name])
        if agent_msg != [] and self.spade_pipe is not None:
            logger.info('Going to push %s to agent queue.', agent_msg)
            self.spade_pipe.send(agent_msg)
            #spade_send_msg(agent_msg)
            #spade_write_file(agent_msg)
        logger.info('AFTER NEW POD DEPLOYMENT')
        # Remove old Pods
        # If redirection is enabled, pass the connection init thread in order to join it.
        if new_deployment_plan['enable_redirection']:
            del_response, agent_msg = check_for_hosts_to_delete(self.apps_dict[app_name], self.nodes['edgenodes'], self._init_connection_thr)
        elif new_deployment_plan['disable_redirection']:
            del_response, agent_msg = check_for_hosts_to_delete(self.apps_dict[app_name], self.nodes['edgenodes'], self._destroy_connection_thr)
        else:
            del_response, agent_msg = check_for_hosts_to_delete(self.apps_dict[app_name], self.nodes['edgenodes'])
        if agent_msg != [] and self.spade_pipe is not None:
            logger.info('Going to push %s to agent queue.', agent_msg)
            self.spade_pipe.send(agent_msg)
            #spade_send_msg(agent_msg)
            #spade_write_file(agent_msg)
        if not del_response:
            logger.info('check_for_hosts_to_delete failed.')
        logger.info('AFTER check_for_hosts_to_delete')
        # Find the current host of image checker
        # And the previous one
        # If they both exist, update the respective entries referring to the adaptation delay.
        # Hold the ending time of adaptation in order to calc the adaptation delay sent via the context.
        total_adaptation_end = time.perf_counter()
        total_adaptation_delay = total_adaptation_end - total_adaptation_start
        
        if self.enable_statistics:
            if src_name == None or dst_name == None:
                logger.error('Statistics error. Src or dst.')
            else:
                self._app_monitor_thr_dict[app_name]['system_metrics']['statistics'][dst_name]['MigrateFrom'][src_name]['CurrentSum'] = \
                self._app_monitor_thr_dict[app_name]['system_metrics']['statistics'][dst_name]['MigrateFrom'][src_name]['CurrentSum'] + total_adaptation_delay
                self._app_monitor_thr_dict[app_name]['system_metrics']['statistics'][dst_name]['MigrateFrom'][src_name]['TotalAdaptations'] = \
                self._app_monitor_thr_dict[app_name]['system_metrics']['statistics'][dst_name]['MigrateFrom'][src_name]['TotalAdaptations'] + 1
                self._app_monitor_thr_dict[app_name]['system_metrics']['statistics'][dst_name]['MigrateFrom'][src_name]['AvgAdaptDelay'] = \
                self._app_monitor_thr_dict[app_name]['system_metrics']['statistics'][dst_name]['MigrateFrom'][src_name]['CurrentSum']/self._app_monitor_thr_dict[app_name]['system_metrics']['statistics'][dst_name]['MigrateFrom'][src_name]['TotalAdaptations']
                self._app_monitor_thr_dict[app_name]['system_metrics']['statistics'][dst_name]['MigrateFrom'][src_name]['RawAdaptDelays'].append(total_adaptation_delay)
        
        self._app_monitor_thr_dict[app_name]['block_monitor_sem'].release()
        self._app_monitor_thr_dict[app_name]['block_resource_checker_sem'].release()

    def _handle_rm_app(self, app_name, app_spec, app_uid):
        """Handle the removal request of an existing application.

        Args:
            app_name (str): The name of the application.
            app_spec (dict): The specification of the application.
        """
        #logger.info('Remove FluidityApp %s\nuid: %s\nspec: %s',
        #            app_name, app_uid, app_spec)
        if app_name in self.apps_dict:
            app_dict = self.apps_dict[app_name]
            for comp_spec in app_spec['components']:
                if 'internal_uid' not in app_dict or app_dict['internal_uid'] == None:
                    continue
                timestamp = datetime.now()
                info = {
                    'status': 'to_be_removed',
                    'timestamp': str(timestamp)
                }
                logger.info('Going to push to redis endpoint_queue the value %s', info)
                # self.redis_hashmap.update_dict_value('endpoint_hash', app_dict['internal_uid'], str(info))
            # Remove depending on state
            if app_dict['state'] == 'APP_EXECUTION':
                self._app_monitor_thr_dict[app_name]['block_monitor_sem'].acquire()
                self._app_monitor_thr_dict[app_name]['block_resource_checker_sem'].acquire()
                ret = delete_running_pods(self.apps_dict[app_name])
                if not ret:
                    logger.error('Pod removal failed.')
                self._app_monitor_thr_dict[app_name]['block_monitor_sem'].release()
                self._app_monitor_thr_dict[app_name]['block_resource_checker_sem'].release()
            logger.info('Going to stop Monitor thread for app: %s', app_name)
            self._app_monitor_thr_dict[app_name]['thread'].stop()
            #logger.info(self.apps_dict)
            for comp_spec in app_spec['components']:
                if 'internal_uid' not in app_dict or app_dict['internal_uid'] == None:
                    continue
                timestamp = datetime.now()
                info = {
                    'status': 'removed',
                    'timestamp': str(timestamp)
                }
                logger.info('Going to push to redis endpoint_queue the value %s', info)
                # self.redis_hashmap.update_dict_value('endpoint_hash', app_dict['internal_uid'], str(info))
            self.apps_dict[app_name].clear()
            del self.apps_dict[app_name]

def main(spade_pipe=None):
    """Main Controller loop."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='Fluidity controller.')
    parser.add_argument('--exec', '-e',
                        default='TEST',
                        help='Execution mode')
    args = parser.parse_args()
    # Overwrite arg if respective environment variable is set
    exec_mode = os.getenv('FLUIDITY_CONTROLLER_EXEC_MODE', args.exec)

    # Configure logging
    logger = logging.getLogger('')
    formatter = logging.Formatter('%(asctime)s %(levelname)s '
                                  '[%(filename)s] %(message)s ')
    f_hdlr = logging.FileHandler('/var/tmp/cluster_agent_fluidity_mlsysops.log')
    f_hdlr.setFormatter(formatter)
    f_hdlr.setLevel(logging.INFO)
    logger.addHandler(f_hdlr)
    s_hdlr = logging.StreamHandler(sys.stdout)
    s_hdlr.setFormatter(formatter)
    s_hdlr.setLevel(logging.INFO)
    logger.addHandler(s_hdlr)
    # logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)

    # Detect if controller is run within a Pod or outside
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()
    # Load kubeconfig from the default location (~/.kube/config)
    # Retrieve the current context and cluster name
    current_context = config.list_kube_config_contexts()[1]  # [0]: All contexts, [1]: Current context
    current_cluster_name = current_context['context']['cluster']

    logger.info(f"Current cluster name: {current_cluster_name}")
    # kube_config = config.kube_config.KubeConfigLoader(config_file="~/.kube/config")
    # logger.info('KUBECONFIG %s', kube_config)
    # Retrieve the current cluster information
    #current_cluster_name = kube_config.context.get('context', {}).get('cluster')

    # Print the cluster name
    if current_cluster_name:
        fluidityapp_settings.cluster_id = current_cluster_name
        logger.info('Current cluster id: %s', fluidityapp_settings.cluster_id)
    else:
        logger.error("Cluster name not found in the kubeconfig.")
        sys.exit(0)

    if spade_pipe is None:
        # If Fluidity is running standalone
        fluidityapp_settings.policy_dir = os.getcwd()+'/../policies/'
        fluidityapp_settings.policy_config_file = os.getcwd()+'/fluidityapp_policy_cfg.yaml'
    else:
        # If the spade agent started Fluidity
        fluidityapp_settings.policy_dir = os.getcwd()+'/fluidity/policies/'
        fluidityapp_settings.policy_config_file = os.getcwd()+'/fluidity/cloud/fluidityapp_policy_cfg.yaml'

    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_app_command', "gauge", IDLE)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_kubernetes_ml_command', "gauge", IDLE)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_classifier_app_deployed', "gauge", IDLE)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_detector_app_deployed', "gauge", IDLE)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_camera_app_deployed', "gauge", IDLE)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_model_deployed', "gauge", IDLE)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_k3s_app_command', "gauge", IDLE)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_k3s_model_command', "gauge", IDLE)
    ensure_crds()
    controller = FluidityAppController(spade_pipe, ExecMode[exec_mode])
    controller.setup()

# async def async_main():
#     main()

if __name__ == '__main__':
    main()

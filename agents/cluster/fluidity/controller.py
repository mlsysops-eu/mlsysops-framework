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
"""Fluidity applications Controller."""
from __future__ import print_function
import argparse
import asyncio
import copy
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from kubernetes import client, config, watch

import kubernetes_asyncio

from kubernetes.client.rest import ApiException
from kubernetes.utils.quantity import parse_quantity
from ruamel.yaml import YAML
import inspect

from mlsysops import MessageEvents
from .crds_config import CRDS_INFO_LIST, API_GROUP
from .objects_api import FluidityObjectsApi, FluidityApiException
from .nodes import get_drones, get_dronestations, get_edgenodes, get_mobilenodes, get_cloudnodes, get_k8s_nodes, get_custom_nodes, \
                                          set_fluiditynode_label, set_node_label, update_app_resources, set_node_annotation
from .deploy import cleanup_pods, delete_running_pods, check_for_hosts_to_delete, create_adjusted_pods_and_configs, \
                                initiate_wifi_connection, destroy_wifi_connection, PROXY_MODE, create_svc, deploy_app_pods_and_configs, \
                                deploy_new_pods, send_notification_to_host, create_pod_object, extend_pod_label_template, \
                                extend_pod_env_template, create_svc_object, create_svc_manifest, create_pod_manifest, \
                                reconfigure_deployment
from .config import append_dict_to_list
from .monitor import FluidityAppMonitor
from .settings import RANGE_WIFI, RANGE_ZIGBEE, RANGE_BLUETOOTH, MOBILE_EDGE_PROXIMITY_RANGE
from .util import FluidityAppInfoDict, FluidityCompInfoDict, FluidityNodeInfoDict
from .geo_util import feature_to_shapely, coords_to_shapely, point_in_area
from .operation_area import get_com_area_edgenode
from .system_statistics import add_statistic_entry, add_migration_entry
import settings as fluidityapp_settings

logger = logging.getLogger(__name__)

class ExecMode(Enum):
    """Enumeration for execution modes."""
    DEV = 'DEV'
    DEPLOY = 'DEPLOY'
    EVAL = 'EVAL'
    TEST = 'TEST'

def start_asyncio_thread():
    loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    return loop, thread  # Return the loop so we can schedule tasks on it

def create_cr(cr_dict, cr_kind):
    api_version = "mlsysops.eu/v1"
    group = "mlsysops.eu"
    version = "v1"
    namespace = "default"

    # Create the API client for Custom Resources
    api = client.CustomObjectsApi()
    # Extract the cluster name and CR kind
    if cr_kind == 'MLSysOpsCluster':
        plural = "mlsysopsclusters"
        # Access the desired field
        cr_name = cr_dict['clusterID']
        logger.info("clusterID: %s", cr_name)
        fluidityapp_settings.cluster_id = cr_name
        logger.info('Current cluster id: %s', fluidityapp_settings.cluster_id)
    else:
        cr_name = cr_dict.pop("name", "")
        plural = "mlsysopnodes"

    # Create a new dictionary with the desired structure
    updated_dict = {
        "apiVersion": "mlsysops.eu/v1",
        "kind": cr_kind,
        "metadata": {
            "name": cr_name
        }
    }
    updated_dict.update(cr_dict)
    logger.info(f'Updated dict {updated_dict}')
    
    try:
        api.create_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=plural,
            body=updated_dict
        )
        logger.info(f"Custom resource {updated_dict['metadata']['name']} created in namespace {namespace}")
    except ApiException as exc:
        logger.error('Create CR %s failed: %s', cr_kind, exc)

def ensure_crds():
    """Ensure all MLSysOps CRDs are registered.

    Checks if the MLSysOps-related resource definitions are registered and
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

    def __init__(self, inbound_queue,outbound_queue, exec_mode=ExecMode.TEST):
        self.mls_inbound_monitor_task = None
        self.exec_mode = exec_mode #: enum: The controller's execution mode
        #: dict: Registered Fluidity apps; key app name - value FluidityAppInfoDict dictionary
        self.apps_dict = {}
        self.nodes = copy.deepcopy(FluidityNodeInfoDict)
        #: dict: Key edgenode name - value dict with keys the intersection with all other nodes
        self.reachable_edgenodes = {}
        self.enable_statistics = False
        self.abort_event = threading.Event() #: Event for clean abort
        self.old_spec = None # For keeping the old app spec if operation:MODIFIED occurs
        self.notification_queue = asyncio.Queue() #: (internal) Application requests queue
        # self.spade_pipe = spade_pipe
        # If no inbound queue is specified, create an internal one 
        if inbound_queue != None:
            self.mls_inbound_queue = inbound_queue
        self.mls_outbound_queue = outbound_queue
        self._app_handler_thr = None #: FluidityApp request handler thread
        self.__app_handler_task = None
        self._app_monitor_thr_dict = {}

    async def _mls_inbound_monitor(self):
        """Monitor MLSysOps inbound queue for messages."""
        logger.info('MLSysOps inbound queue monitor started')
        while True:
            try:
                message = await self.mls_inbound_queue.get()
                logger.info('Received from MLSysOps queue msg: %s', message)
                event = message.get("event")
                data = message.get("payload")

                # Submit node and cluster CR in the k8s api
                if event == MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMIT.value:
                    logger.debug(f"Received node system CR")
                    for cr_entry in data:
                        logger.info(f'Found CR with name {cr_entry}')
                        create_cr(data[cr_entry], cr_entry)
                    continue

                name = data.get("name")
                # spec = data.get("spec")
                # uid = data.get("uid")

                if event is None or data is None or name is None:
                    logger.info('Ignoring message: One of event/data/name is missing.')
                    continue

                if event == MessageEvents.PLAN_SUBMITTED.value:
                    logger.info('RECEIVED PLAN_SUBMITTED EVENT')
                    plan = data.get("deployment_plan")
                    if plan == None:
                        logger.error('No plan specified. Going to continue')
                        continue
                    if name is None:
                        logger.error('[%s]: APP FIELD IS NONE.')
                    elif name not in self.apps_dict:
                        logger.error('[%s]: APP %s IS NOT IN THE APP DICT.', inspect.currentframe().f_code.co_name,
                                     name)
                elif event == 'plan_executed':
                    pass

                else:
                    logger.error(f"Unhandled event type: {event}")
                
                msg = {
                    'operation': event,
                    'origin': 'spade',
                    'payload': {
                        'name': name,
                        'deployment_plan': plan,
                    }
                }
                logger.info('inbound_monitor: Going to push through notification_queue %s', msg)
                await self.notification_queue.put(msg)
            except Exception as e:
                logger.error(f"Error in MLSysOps monitor: {e}")
                await asyncio.sleep(1)

    async def setup(self):
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
        

        self.__app_handler_task = asyncio.create_task(self._app_handler())
        logger.info('Creating thread to communicate with SPADE agent')
        self.mls_inbound_monitor_task = asyncio.create_task(self._mls_inbound_monitor())
        #await self.mls_inbound_monitor_task
        # Start main control loop
        control_task = asyncio.create_task(self.control_loop())
        # Worker loop and thread
        #worker_loop = asyncio.new_event_loop()
        #thread = threading.Thread(target=self.start_new_event_loop, args=(worker_loop,), daemon=True).start()
        #loop, thread = start_asyncio_thread()
        #future = asyncio.run_coroutine_threadsafe(self._mls_inbound_monitor(), loop)
        # Schedule the coroutine from the main thread
        #asyncio.run_coroutine_threadsafe(self._mls_inbound_monitor(), worker_loop)
        #loop.close()
        await control_task

    def _setup_drones(self):
        """Setup drone and dronestations-related resources.

        Adds and updates Fluidity-related fields, labels and annotations to
        drone (mlsysops.eu/drone-station, mlsysops.eu/direct-range)
        dronestation (drone names)
        and node k8s objects (mlsysops.eu/node-type,mlsysops.eu/node-spec,
        mlsysops.eu/drone-station,mlsysops.eu/direct-range).
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
                                'mlsysops.eu/drone-station',
                                station['metadata']['name'])
                station_name = station['metadata']['name']
                # NOTE: Add separate labels to support multiple net technologies
                set_fluiditynode_label(drone['metadata']['name'],
                                'mlsysops.eu/direct-range',
                                str(max_net_range))
                break
            # Map drone to k8s node
            # NOTE: Commented out this for the test/evaluation
            if self.exec_mode not in [ExecMode.TEST, ExecMode.EVAL]:
                for node in self.nodes['k8snodes']:
                    if node.metadata.name == drone['metadata']['name']:
                        set_node_label(node.metadata.name,
                                       'mlsysops.eu/node-type',
                                       'drone')
                        set_node_annotation(node.metadata.name,
                                            'mlsysops.eu/node-spec',
                                            json.dumps(drone['spec']))
                        # NOTE: Add separate labels to support multiple net technologies
                        set_node_label(node.metadata.name,
                                       'mlsysops.eu/direct-range',
                                       str(max_net_range))
                        if station_name is None:
                            break
                        set_node_label(node.metadata.name,
                                       'mlsysops.eu/drone-station',
                                       station_name)
                        break

    def _setup_edgenodes(self):
        """Setup edgenode-related resources.

        Adds and updates Fluidity-related labels and annotations to
        edgenode (mlsysops.eu/direct-range)
        and node k8s objects (mlsysops.eu/node-type,mlsysops.eu/node-spec,
        mlsysops.eu/direct-range).
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
                               'mlsysops.eu/direct-range',
                               str(max_net_range))
             # NOTE: Commented out this for the test/evaluation
            if self.exec_mode not in [ExecMode.TEST, ExecMode.EVAL]:
                for node in self.nodes['k8snodes']:
                    if node.metadata.name == edgenode['metadata']['name']:
                        set_node_label(node.metadata.name,
                                       'mlsysops.eu/node-type',
                                       'edgenode')
                        set_node_annotation(node.metadata.name,
                                            'mlsysops.eu/node-spec',
                                            json.dumps(edgenode['spec']))
                        # NOTE: Add separate labels for different net technologies
                        set_node_label(node.metadata.name,
                                       'mlsysops.eu/direct-range',
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

    async def control_loop(self):
        """Main control loop of the FluidityApp controller.

        Watches for fluidityapps resources and inserts them in the
        :py:attr:`~notification_queue`.
        """
        resource_version = None  # Start with 'None' to fetch the latest events
        #resource_version = ''
        while True:
            async with kubernetes_asyncio.client.ApiClient() as api_client:
                co_api = kubernetes_asyncio.client.CustomObjectsApi(api_client)
                try:
                    # Watch for fluidityapps resources
                    async with kubernetes_asyncio.watch.Watch().stream(
                            co_api.list_cluster_custom_object,
                            API_GROUP,
                            'v1',
                            'mlsysopsapps',
                            resource_version=resource_version or '',
                            timeout_seconds=60) as stream:
                        async for event in stream:
                            # Extract event details
                            operation = event['type']
                            obj = event['object']
                            metadata = obj.get('metadata', {})
                            app_name = metadata.get('name')
                            app_uid = metadata.get('uid')
                            resource_version = metadata.get('resourceVersion', resource_version)

                            logger.info('Handling %s on %s', operation, app_name)
                            logger.info('UID: %s', app_uid)

                            # Check if the app is not already in the dictionary
                            if app_name and app_name not in self.apps_dict:
                                logger.info('New app detected: %s - not in apps_dict', app_name)
                            # FOR TESTING
                            # if app_name != 'default-augmenta-app':
                            #     logger.info('Testing: Ignoring app with name != default-augmenta-app')
                            #     continue
                            app_req = {
                                'type': 'app-desc',
                                'origin': 'internal',
                                'operation': operation,
                                'name': app_name,
                                'spec': obj,
                                'uid': app_uid
                            }

                            # Add the app request to the notification queue
                            await self.notification_queue.put(app_req)
                #
                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt, shutting down watcher.")
                    break
                except kubernetes_asyncio.client.exceptions.ApiException as exc:
                    logger.error('Kubernetes API exception while watching FluidityApps: %s', exc)
                    await asyncio.sleep(5)  # Retry after a short delay
                except Exception as e:
                    logger.error('Unexpected exception encountered: %s', e)
                    await asyncio.sleep(5)  # Retry after a short delay
                finally:
                    # Ensure the watcher is properly closed
                    logger.info('Watcher stream closed.')

    async def _app_handler(self):
        """FluidityApp handler thread.

        Receives application deployment requests through the
        :py:attr:`~notification_queue` and serves them one at a time by invoking
        the respective handling method. It exits in case the abort event is set.
        """
        logger.info('AppHandler thread started')
        while True:
            try:
                req = await self.notification_queue.get()
                logger.info('App handler received %s', req['operation'])
                origin = req.get("origin")
                payload = req.get("payload")
                plan_uuid = None
                if origin == 'internal':
                    app_name = req.get("name")
                    app_spec = req.get("spec")
                    app_uid = req.get("uid")
                elif origin == 'spade':
                    app_name = payload.get("name")
                    plan = payload.get("deployment_plan")
                    plan_uuid = payload.get("plan_uuid")
                    logger.info("plan_uuid %s", plan_uuid)
                    if plan:
                        initial_plan = plan.get("initial_plan")
                
                agent_msg = {}

                if req['operation'] == 'ADDED':
                    await self._handle_add_app(req['name'], req['spec'], req['uid'])
                elif req['operation'] == 'MODIFIED':
                    agent_msg["event"] = MessageEvents.APP_UPDATED.value
                    agent_msg['payload'] = {
                        'name': app_name,
                        'spec': app_spec
                    }
                    #logger.info('Fluidity new spec %s', app_spec)
                    self.apps_dict[app_name]['spec'] = app_spec
                    await self.mls_outbound_queue.put(agent_msg)
                elif req['operation'] == 'DELETED':
                    await self._handle_rm_app(req['name'], req['spec'], req['uid'])
                elif req['operation'] == MessageEvents.PLAN_SUBMITTED.value:
                    
                    if payload is None or app_name is None or plan is None or plan == {}:
                        logger.info('payload, app name or plan is empty.')
                        continue
                    result = None
                    logger.info("initial_plan %s",initial_plan)
                    if initial_plan:
                        plan.pop('initial_plan')
                        for comp_name in plan:
                            for action_entry in plan[comp_name]:
                                action_entry['status'] = 'PENDING'
                        logger.debug('Created plan %s', plan)
                        self.apps_dict[app_name]['curr_plan']['curr_deployment'] = plan
                        self.apps_dict[app_name]['state'] = 'APP_DEPLOYMENT'

                        deployment, comp_dict = deploy_app_pods_and_configs(self.apps_dict[app_name], self.apps_dict[app_name]['curr_plan']['curr_deployment'])
                        #logger.info(f'Fluidity is going to send {comp_dict}')
                        start_monitor = await self.start_monitor_and_update_internal_structures(app_name)
                        if deployment and start_monitor:
                            logger.info('Going to push %s to agent queue.', comp_dict)
                            status = 'SUCCESS'
                            self.apps_dict[app_name]['initial_plan_completed'] = True
                        else:
                            logger.error('Initial deployment failed.')
                            status = 'FAILURE'
                        agent_msg["event"] = MessageEvents.COMPONENT_PLACED.value
                        agent_msg["payload"] = {
                            "name" : app_name,
                            "status": status,
                            "plan_uuid": plan_uuid,
                            "comp_dict": comp_dict
                        }
                        await self.mls_outbound_queue.put(agent_msg)
                    else:
                        logger.info('Received reconfiguration request %s', plan)
                        logger.info('curr plan %s', self.apps_dict[app_name]['curr_plan']['curr_deployment'])
                        # Extra check so that no adaptation is made if the initial plan is not executed
                        if self.apps_dict[app_name]['initial_plan_completed'] is not True:
                            logger.info('Initial deployment is not executed. Ignoring...')
                            continue
                        plan.pop('initial_plan')
                        self.apps_dict[app_name]['curr_plan']['curr_deployment'] = plan
                        await self._handle_upd_app(app_name, self.apps_dict[app_name]['spec'], self.apps_dict[app_name]['uid'])
                else:
                    logger.info('AppHandler: No event in notification_queue (ignored).')
            except Exception as e:
                logger.exception("Error handling app request: %s", e)

    async def _handle_add_app(self, app_name, app_spec, app_uid):
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
        app_dict['initial_plan_completed'] = False

        # MLS: remove policy
        # logger.info(app_dict['name'])
        # logger.info(app_dict['uid'])
        # logger.info(app_dict['spec'])

        app_dict['reachable_edgenodes'] = self.reachable_edgenodes

        logger.info('No policies in fluidity.')
        logger.info('Cluster id: %s', fluidityapp_settings.cluster_id)
        
        tmp_cluster_id = None
        if 'clusterPlacement' in app_spec:
            logger.info('Parsing clusterPlacement')
            if 'clusterID' in app_spec['clusterPlacement']:
                # Selecting the first cluster
                tmp_cluster_id = app_spec['clusterPlacement']['clusterID'][0]
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
                # logger.info(comp_name)
                # logger.info(svc_obj.spec.cluster_ip)
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
        
        ## Wait for initial deployment here from policy plugin
        agent_msg = {
            'event': MessageEvents.APP_CREATED.value,
            'payload': {
                'name': app_name,
                'spec': app_spec,
                'uid': app_uid
            }
        }
        logger.debug('Going to push %s', agent_msg)
        await self.mls_outbound_queue.put(agent_msg)

    async def start_monitor_and_update_internal_structures(self, app_name):
        #print(self.apps_dict)
        #Translation of the initial_plan()s output
        initial_plan = self.apps_dict[app_name]['curr_plan']['curr_deployment']
        #initial_plan.pop('initial_plan')
        for comp_name in initial_plan:
            logger.info('Initial deployment %s' % comp_name)
            comp_spec = self.apps_dict[app_name]['components'][comp_name]
            host_name = initial_plan[comp_name][0]['host']
            logger.info('Initial host %s' % host_name)
            for node in self.nodes['cloudnodes']:
                if node['metadata']['name'] == host_name:
                    self.apps_dict[app_name]['cloud_comp_names'].append(comp_spec['name'])
                    self.apps_dict[app_name]['cloud_comp_specs'].append(comp_spec)
                    comp_spec['placement'] = 'cloud'
                    break
            #logger.info(self.nodes['edgenodes'])
            for node in self.nodes['edgenodes']:
                if node['metadata']['name'] == host_name:
                    self.apps_dict[app_name]['edge_comp_names'].append(comp_spec['name'])
                    self.apps_dict[app_name]['edge_comp_specs'].append(comp_spec)
                    comp_spec['placement'] = 'edge'
                    #logger.info('comp spec: %s', comp_spec)
                    break
            for node in self.nodes['mobilenodes']:
                if node['metadata']['name'] == host_name:
                    self.apps_dict[app_name]['mobile_comp_names'].append(comp_spec['name'])
                    self.apps_dict[app_name]['mobile_comp_specs'].append(comp_spec)
                    comp_spec['placement'] = 'mobile'
                    break
            for node in self.nodes['cloudnodes']:
                if node['metadata']['name'] == host_name:
                    self.apps_dict[app_name]['cloud_comp_names'].append(comp_spec['name'])
                    self.apps_dict[app_name]['cloud_comp_specs'].append(comp_spec)
                    comp_spec['placement'] = 'cloud'
                    break
            if comp_name in self.apps_dict[app_name]['hybrid_mobile_comp_names']:
                # Check if a cloud node will host the hybrid component.
                for node in self.nodes['cloudnodes']:
                    if node['metadata']['name'] == host_name:
                        comp_spec['host_hybrid_cloud'] = host_name
                        #logger.info(comp_spec['host_hybrid_cloud'])
                        break

        self.apps_dict[app_name]['state'] = 'APP_EXECUTION'
        # Create fluidityapp monitor thread and insert it to the list
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
        app_monitor = FluidityAppMonitor(self.apps_dict[app_name], self.nodes,
                                            self.notification_queue, self.apps_dict[app_name]['context'], system_metrics)
        tmp_dict = {
            'system_metrics': system_metrics,
            "app_monitor": app_monitor,
            "task": asyncio.create_task(app_monitor.run())
        }
        logger.info(f"adding {app_name}")
        self._app_monitor_thr_dict[app_name] = tmp_dict
        return True

    async def _handle_upd_app(self, app_name, new_app_spec, app_uid, spade_request=None):
        """Handle the update request for an existing application.

        Args:
            app_name (str): The name of the application.
            new_app_spec (dict): The (possibly) new specification of the application.
            app_uid (str): The app uid for app management within Fluidity.
            spade_request (list): List of updated Pod specs sent by an MLSysOps agent.
        """
        # Hold the starting time of adaptation in order to calc the adaptation delay sent to the context
        total_adaptation_start = time.perf_counter()
        new_deployment_plan = self.apps_dict[app_name]['curr_plan']
        # Update the app_spec and the deployment plan
        self.apps_dict[app_name]['spec'] = new_app_spec
        #self.apps_dict[app_name]['curr_plan'] = new_deployment_plan
        agent_msg = {
            "event": MessageEvents.PLAN_EXECUTED.value
        }
        agent_msg["payload"] = {
            "name" : app_name,
            "status": 'SUCCESS',
            "plan_uuid": '',
            "comp_dict": None
        }
        comp_dict = {
            'specs': []
        }
        tmp_dict = {}

        for comp_name in new_deployment_plan['curr_deployment']:
            comp_spec = self.apps_dict[app_name]['components'][comp_name]
            updated_hosts = False
            for entry in new_deployment_plan['curr_deployment'][comp_name]:
                action = entry['action']
                # For deploy or remove actions.
                host = None
                # For move action.
                move_src_host = None
                move_target_host = None
                if action == 'move':
                    # move_src_host = new_deployment_plan['curr_deployment'][comp_name][entry]['src_host']
                    # move_target_host = new_deployment_plan['curr_deployment'][comp_name][entry]['target_host']
                    move_src_host = entry['src_host']
                    move_target_host = entry['target_host']
                    logger.info(f'Caught move cmd of {comp_name} from {move_src_host} to {move_target_host}')
                    logger.info('comp_spec[hosts]: %s', comp_spec['hosts'])
                    append_dict_to_list({'host': move_src_host, 'status': 'INACTIVE'}, comp_spec['hosts'])
                    append_dict_to_list({'host': move_target_host, 'status': 'PENDING'}, comp_spec['hosts'])
                    updated_hosts = True
                elif action == 'deploy' or action == 'remove':
                    host = new_deployment_plan['curr_deployment'][comp_name][entry]['host']
                    entry['host']
                    status = 'INACTIVE'
                    if action == 'deploy':
                        status = 'PENDING'
                    append_dict_to_list({'host': host, 'status': status}, comp_spec['hosts'])
                    logger.info(comp_spec['hosts'])
                    updated_hosts = True
                elif action == 'change_img':
                    result, updated_spec = reconfigure_deployment(self.apps_dict[app_name], new_deployment_plan['curr_deployment'])
                    if result:
                        logger.info('Modified Pod specs accordingly.')
                    else:
                        logger.error('Pod spec modification failed')
                        agent_msg["payload"]["status"] = 'FAILURE'

                    tmp_dict[comp_name] = copy.deepcopy(comp_dict)
                    tmp_dict[comp_name]['specs'].append(updated_spec)
                    agent_msg["payload"]["comp_dict"] = tmp_dict
                    logger.info('Going to push %s to agent queue.', agent_msg)
                    await self.mls_outbound_queue.put(agent_msg)
                else:
                    logger.error('Policy provided invalid action. Going to return.')
                    return
            if updated_hosts:
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
        # TODO Change this accordingly.
        if agent_msg != [] and self.mls_outbound_queue is not None:
            logger.info('Going to push %s to agent queue.', agent_msg)
            await self.mls_outbound_queue.put(agent_msg)
        logger.info('AFTER NEW POD DEPLOYMENT')
        # Remove old Pods
        # If redirection is enabled, pass the connection init thread in order to join it.
        if new_deployment_plan['enable_redirection']:
            del_response, agent_msg = check_for_hosts_to_delete(self.apps_dict[app_name], self.nodes['edgenodes'], self._init_connection_thr)
        elif new_deployment_plan['disable_redirection']:
            del_response, agent_msg = check_for_hosts_to_delete(self.apps_dict[app_name], self.nodes['edgenodes'], self._destroy_connection_thr)
        else:
            del_response, agent_msg = check_for_hosts_to_delete(self.apps_dict[app_name], self.nodes['edgenodes'])
        if agent_msg != [] and self.mls_outbound_queue is not None:
            logger.info('Going to push %s to agent queue.', agent_msg)
            await self.mls_outbound_queue.put(agent_msg)
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
        


    async def _handle_rm_app(self, app_name, app_spec, app_uid):
        """Handle the removal request of an existing application.

        Args:
            app_name (str): The name of the application.
            app_spec (dict): The specification of the application.
        """
        #logger.info('Remove FluidityApp %s\nuid: %s\nspec: %s',
        #            app_name, app_uid, app_spec)
        if app_name in self.apps_dict:
            app_dict = self.apps_dict[app_name]
            # Remove depending on state
            #if app_dict['state'] == 'APP_EXECUTION':
            ret = delete_running_pods(self.apps_dict[app_name])
            if not ret:
                logger.error('Pod removal failed.')
            logger.info('Going to stop Monitor thread for app: %s', app_name)
            self._app_monitor_thr_dict[app_name]['task'].cancel()

            if self.mls_outbound_queue is not None:
                logger.info('Going to push %s deletion to agent queue.', app_name)
                await self.mls_outbound_queue.put({"event": MessageEvents.APP_DELETED.value, "payload": app_name})
                # for pod_name in self.apps_dict[app_name]['pod_names']:
                #     await self.mls_outbound_queue.put({"event": MessageEvents.COMPONENT_REMOVED.value,
                #                                     "payload": dict({"name": pod_name})})
            #logger.info(self.apps_dict)
            self.apps_dict[app_name].clear()
            del self.apps_dict[app_name]

async def main(inbound_queue=None, outbound_queue=None):
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
    logger.setLevel(logging.DEBUG)
    #logger.setLevel(logging.INFO)
    await kubernetes_asyncio.config.load_config()

    # Detect if controller is run within a Pod or outside
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()
        await kubernetes_asyncio.config.load_kube_config()


    # Load kubeconfig from the default location (~/.kube/config)
    # Retrieve the current context and cluster name
    #current_context = config.list_kube_config_contexts()[1]  # [0]: All contexts, [1]: Current context
    # cluster_desc = _apply_cluster_description()
    # if not cluster_desc:
    #     logger.error("Error on applying cluster description")
    #     sys.exit(0)
    # else:
    #     fluidityapp_settings.cluster_id = cluster_desc['clusterID']
    #     logger.info('Current cluster id: %s', fluidityapp_settings.cluster_id)

    #ensure_crds() # TODO maybe we need to remove it, as it comes from continuum
    controller = FluidityAppController(inbound_queue,outbound_queue, ExecMode[exec_mode])
    await controller.setup()


if __name__ == '__main__':
    asyncio.run(main())

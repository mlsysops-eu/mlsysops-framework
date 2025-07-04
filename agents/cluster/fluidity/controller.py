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
import kubernetes_asyncio
import socket
import yaml
import watcher
import cluster_config

from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.utils.quantity import parse_quantity
from ruamel.yaml import YAML
from deepdiff import DeepDiff
from mlsysops.data.task_log import Status
from mlsysops import MessageEvents
from mlsysops.logger_util import logger
from cluster_config import CRDS_INFO_LIST, API_GROUP, VERSION
from objects_api import FluidityObjectsApi, FluidityApiException
from fluidity_monitor import FluidityMonitor
from util import FluidityAppInfoDict, FluidityCompInfoDict
from objects_util import get_crd_info
from spade_msg import PodDict, CompDict, EventDict, create_pod_dict, create_msg
from dict_diff import DeepDiffPathApplier


from nodes import append_host_to_list, get_k8s_nodes, get_custom_nodes, get_mls_nodes, \
                  update_resource, delete_resource

from deploy import cleanup_pods, delete_running_pods, check_for_hosts_to_delete, \
                   create_adjusted_pods_and_configs, create_svc, deploy_app_pods_and_configs, \
                   deploy_new_pods, create_pod_object, extend_pod_label_template, \
                   extend_pod_env_template, create_svc_object, create_svc_manifest, \
                   create_pod_manifest, change_comp_spec, validate_host


def check_diff(d1, d2):
    diff = DeepDiff(d1, d2)
    #logger.info(f'diff {diff}')

    # Prepare applier with source = d2
    applier = DeepDiffPathApplier(d2)

    # Apply new keys
    applier.apply_added_paths(d1, diff.get('dictionary_item_added', set()))

    # Remove deleted keys
    applier.remove_deleted_paths(d1, diff.get('dictionary_item_removed', set()))

    # Apply changed values
    applier.apply_value_changes(d1, diff.get('values_changed', {}))

    #logger.info(json.dumps(d1, indent=2))
    if 'dictionary_item_added' in diff or 'dictionary_item_removed' in diff or \
        'values_changed' in diff:
        # logger.info('Found diff in dicts')
        return True

    logger.info(f'No changes found in dicts')    
    return False

def translate_plan(new_deployment_plan, old_specs, new_specs=None):
    # If app desc modified, we compare the new app desc with the internal one
    # Otherwise, we compare the deployment_plan with the internal one

    app_modified = True if new_specs else False
    change_found = False
    change_spec_action = False

    if not app_modified:
        logger.info('New policy plan for change spec')
        # logger.debug(f'new_deployment_plan {new_deployment_plan}')
        new_specs = []

        for comp in new_deployment_plan['curr_deployment']:
            for entry in new_deployment_plan['curr_deployment'][comp]:
                if entry['action'] == 'change_spec':
                    # May also need to add name.
                    new_specs.append(entry['new_spec'])
                    change_spec_action = True
    
    for component in new_specs:
        comp_name = component['metadata']['name']

        old_spec = None
        for temp_comp in old_specs:
            if temp_comp == comp_name:
                old_spec = old_specs[temp_comp]
                break

        if not old_spec:
            logger.error(f'Did not find old_spec')
            return False

        new_spec = copy.deepcopy(FluidityCompInfoDict)
        new_spec['spec'] = copy.deepcopy(component)
        new_spec['name'] = comp_name
        new_spec['pod_template'] = create_pod_manifest(new_spec, old_spec['pod_template'])
        # logger.debug(f"old template {old_spec['pod_template']}")
        # logger.debug(f"new template {new_spec['pod_template']}")
        result = check_diff(old_spec['pod_template']['spec'], new_spec['pod_template']['spec'])
        if not result:
            logger.info('Pod specs do not diff.')
            continue

        change_found = True
        
        if app_modified:
            node_name = None
            # Host check when app desc modified
            node_placement = component.get("node_placement", None)
            if node_placement:
                node_name = node_placement.get("node", None)
            
            if not node_name:
                for host in old_spec['hosts']:
                    # Get the first active host
                    if host['status'] == 'ACTIVE':
                        node_name = host['host']
                        break

                logger.info(f'Description did not specified node placement for comp {comp_name}')
                logger.info(f'Will use current host {node_name}')
            else:
                logger.info(f'Description specified node placement {node_name} for comp {comp_name}')

            if not node_name:
                logger.error('Did not find host.')
                return False
            
            action_dict = {'action': 'change_spec', 'new_spec': new_spec['pod_template'], 'host': node_name}
            new_deployment_plan['curr_deployment'][comp_name] = [action_dict]   
        else:
            for comp in new_deployment_plan['curr_deployment']:
                #logger.info(f'comp {comp}')
                if comp != comp_name:
                    continue

                for entry in new_deployment_plan['curr_deployment'][comp_name]:
                    if entry['action'] == 'change_spec':
                        #logger.info(f'UPDATING SPECC for {comp}')
                        entry['new_spec'] = new_spec['pod_template']
                        change_spec_action = True
    
    # If change spec requested and translation no diff found, return False.
    if not change_found and change_spec_action:
        logger.error('New specs do not differ from the old ones. Returning False')
        return False

    # logger.debug(f"Final deployment plan {new_deployment_plan}")
    return True

def get_value_from_path(d, path):
    keys = re.findall(r"\['(.*?)'\]", path)
    current = d
    for k in keys:
        current = current[k]
    return current


def load_custom_resource(filepath):
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)
    return data

def create_cr(cr_dict, cr_kind):
    # Create the API client for Custom Resources
    api = client.CustomObjectsApi()
    

    # Extract the cluster name and CR kind
    if cr_kind == 'MLSysOpsNode':
        plural = "mlsysopsnodes"
        cr_name = cr_dict.pop("name", "")
    elif cr_kind == 'MLSysOpsCluster':
        plural = "mlsysopsclusters"
        cr_name = cr_dict["cluster_id"]
    else:
        logger.error('create_cr: Invalid CR kind.')
        return
    
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
    
    resp = None
    try:
        logger.info('Trying to read cr_kind %s with name %s if already exists', cr_kind, cr_name)
        resp = api.get_namespaced_custom_object(
            name=cr_name,
            group=API_GROUP,
            version=VERSION,
            namespace=cluster_config.NAMESPACE,
            plural=plural)
    except ApiException as exc:
        if exc.status != 404:
            logger.error('Unknown error reading service: %s', exc)
            return None
    if resp:
        try:
            logger.info('Trying to delete cr %s as it already exists', cr_name)
            resp = api.delete_namespaced_custom_object(
                name=cr_name,
                group=API_GROUP,
                version=VERSION,
                namespace=cluster_config.NAMESPACE,
                plural=plural)
        except ApiException as exc:
            logger.error('Failed to delete service: %s', exc)

    try:
        api.create_namespaced_custom_object(
            group=API_GROUP,
            version=VERSION,
            namespace=cluster_config.NAMESPACE,
            plural=plural,
            body=updated_dict
        )
        logger.info(f"Custom resource {updated_dict['metadata']['name']} created in namespace {cluster_config.NAMESPACE}")
    except ApiException as exc:
        logger.error('Create CR %s failed: %s', cr_kind, exc)


def apply_cluster_description(fpath=None, file=None):
    """Apply MLSysOpsCluster CR only if it does not already exist.
    """
    cr_api = FluidityObjectsApi()
    if fpath:
        # Load file from fpath and retrieve name.
        data = load_custom_resource(fpath)
    else:
        data = file
    plural = "mlsysopsclusters"
    exists, crd_info = get_crd_info(plural)
    if not exists:
        logger.error(f'CRD with plural {plural} does not exist')

    cr_dict = data['MLSysOpsCluster']
    cr_name = cr_dict.pop("name", None)

    if not cr_name:
        logger.error(f'Did not find CR name in file {fpath}')
        return None

    # Create a new dictionary with the desired structure
    updated_dict = {
        "apiVersion": "mlsysops.eu/v1",
        "kind": crd_info['kind'],
        "metadata": {
            "name": cr_name
        }
    }

    updated_dict.update(cr_dict)
    logger.info(f'Updated dict {updated_dict}')
    
    resp = None
    try:
        resp = cr_api.get_fluidity_object(plural, cr_name)
    except FluidityApiException:
        logger.error('Retrieving %s failed', cr_name)

    if resp:
        return resp['metadata']['name']

    try:
        crs = cr_api.create_fluidity_object(plural, updated_dict)
    except FluidityApiException:
        logger.error('Creating %s failed', cr_name)
        return None
    
    return updated_dict['metadata']['name']


def create_mls_namespace(mls_namespace):
    """Create MLSysOps namespace if it does not exist.
    """
    # Define the namespace metadata
    namespace = client.V1Namespace(
        metadata=client.V1ObjectMeta(name=mls_namespace)
    )

    # Create the namespace using CoreV1Api
    v1 = client.CoreV1Api()

    try:
        response = v1.create_namespace(body=namespace)
    except ApiException as exc:
        logger.error('Failed to create namespace: %s', exc)

    logger.info(f"Namespace created: {response.metadata.name}")

def namespace_exists(name):
    v1 = client.CoreV1Api()

    try:
        namespaces = v1.list_namespace().items
    except ApiException as exc:
        logger.error('Failed to create namespace: %s', exc)

    return any(ns.metadata.name == name for ns in namespaces)

def update_comp_type(app, comp_spec, type):
    logger.info('update_comp_type')
   
    if type+'_comp_names' not in app:
        app[type+'_comp_names'] = []
        app[type+'_comp_specs'] = []

    if type == '*':
        type = 'generic'
    
    app[type+'_comp_names'].append(comp_spec['name'])
    app[type+'_comp_specs'].append(comp_spec)

def get_node_type(host_name, nodes):
    for type in nodes['mlsysops']:
        for node in nodes['mlsysops'][type]:
            if node['metadata']['name'] == host_name:
                return type

def update_comp_placement(nodes, comp_spec, host_name):
    logger.info('update_comp_placement')
    type = get_node_type(host_name, nodes)

    if not type:
        type = 'generic'

    if type not in comp_spec['placement']:
        comp_spec['placement'].append(type)


def find_enum_for_field(d, target_field):
    results = []
    
    def recurse(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == target_field:
                    #logger.info(f'find_enum_for_field {target_field}')
                    if isinstance(v, dict) and 'items' in v and 'enum' in v['items']:
                        results.append(v['items']['enum'])
                        return True
                    elif isinstance(v, dict) and 'enum' in v:
                        results.append(v['enum'])
                        return True
                # recurse into nested dict or list
                if recurse(v):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                recurse(item)

    recurse(d)
    return results

def get_description_constraints():
    # API client for CRDs
    apiextensions = client.ApiextensionsV1Api()
    crd_name = 'mlsysopsapps.mlsysops.eu'
    # Key is the field name, value the permitted strings retrieved via the CRD.
    constraints = {}
    # Fetch the CRD
    crd = apiextensions.read_custom_resource_definition(crd_name)

    for version in crd.spec.versions:
        if version.name == VERSION:
            # Read CRD
            schema = version.schema.open_apiv3_schema.to_dict()
    # Extract possible fields
    enums = find_enum_for_field(schema['properties'], 'runtime_class_name')
    
    if enums:
        constraints['runtime_class_name'] = enums[0]
    else:
        logger.info("No enum found for runtime_class_name")
    
    return constraints

def create_node_type_dict():
    # API client for CRDs
    apiextensions = client.ApiextensionsV1Api()
    crd_name = 'mlsysopsapps.mlsysops.eu'
    nodes = {}
    # Fetch the CRD
    crd = apiextensions.read_custom_resource_definition(crd_name)

    for version in crd.spec.versions:
        if version.name == VERSION:
            # Read CRD
            schema = version.schema.open_apiv3_schema.to_dict()
    # Extract possible fields
    enums = find_enum_for_field(schema['properties'], 'continuum_layer')
    
    if enums:
        nodes['mlsysops'] = {}
        for enum_list in enums:
            if '*' in enum_list:
                enum_list.remove('*')
            for entry in enum_list:
                # create dict with kubernetes and mlsysops nodes.
                nodes['mlsysops'][entry] = {}
        
    else:
        logger.info("No enum found for 'continuum_layer'")
    
    return nodes, enums[0]


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

def has_egress_relation(app_spec, comp_name):
    """
    Check whether the component receives traffic from another one, thus needed
    to create a corresponding service.
    """
    # Extend component Pod template manifests/objects with Fluidity-related info
    if 'component_interactions' in app_spec:
        for interaction in app_spec['component_interactions']:
            if interaction['type'] == 'egress' and comp_name == interaction['component_name2'] \
            or interaction['type'] == 'ingress' and comp_name == interaction['component_name1']:
                return True
    
    return False

class FluidityAppController():
    """Controller of FluidityApp objects."""

    def __init__(self, inbound_queue,outbound_queue):
        self.mls_inbound_monitor_task = None
        #: dict: Registered Fluidity apps; key app name - value FluidityAppInfoDict dictionary
        self.apps_dict = {}
        #: dict: Key edgenode name - value dict with keys the intersection with all other nodes
        self.notification_queue = asyncio.Queue() #: internal requests queue
        # If no inbound queue is specified, create an internal one 
        if inbound_queue != None:
            self.mls_inbound_queue = inbound_queue
        self.mls_outbound_queue = outbound_queue
        self.__app_handler_task = None #: FluidityApp request handler task
        self._system_monitor_task = None #: FluidityMonitor request handler task
        self._app_monitor_thr_dict = {}

    async def _mls_inbound_monitor(self):
        """Monitor MLSysOps inbound queue for messages."""
        logger.info('MLSysOps inbound queue monitor started')
        while True:
            try:
                message = await self.mls_inbound_queue.get()
                event = message.get("event")
                data = message.get("payload")
                logger.debug('Received from MLSysOps queue msg: %s', event)

                # Submit node and cluster CR in the k8s api
                if event == MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMITTED.value or \
                   event == MessageEvents.CLUSTER_SYSTEM_DESCRIPTION_SUBMITTED.value:
                    logger.debug(f"Received node system CR")
                    for cr_entry in data:
                        logger.info(f'Found CR with name {cr_entry}')
                        create_cr(data[cr_entry], cr_entry)
                    continue

                name = data.get("name")

                if event is None or data is None or name is None:
                    logger.info('Ignoring message: One of event/data/name is missing.')
                    continue

                if event == MessageEvents.PLAN_SUBMITTED.value:
                    plan = data.get("deployment_plan")
                    plan_uid = data.get("plan_uid")
                    logger.test(f"|1| Fluidity controller received planuid:{plan_uid} from MLSAgent status:True")

                    if plan == None:
                        logger.error('No plan specified. Going to continue')
                        continue
                    if name is None:
                        logger.error('APP FIELD IS NONE.')
                    elif name not in self.apps_dict:
                        logger.error('APP %s IS NOT IN THE APP DICT.', name)
                elif event == MessageEvents.PLAN_EXECUTED.value:
                    pass

                else:
                    logger.error(f"Unhandled event type: {event}")
                
                msg = {
                    'operation': event,
                    'origin': 'spade',
                    'payload': {
                        'name': name,
                        'plan_uid': plan_uid,
                        'deployment_plan': plan,
                    }
                }
                # logger.debug('inbound_monitor: Going to push through notification_queue %s', msg)
                await self.notification_queue.put(msg)
            except Exception as e:
                logger.error(f"Error in MLSysOps monitor: {e}")
                await asyncio.sleep(1)

    async def setup(self):
        """Initialize internal structures, setup k8s objects and start main
        control loop.

        Invokes : py:meth:`watch_app`.

        NOTE: The lists keep cached data and should be retrieved/updated
        whenever a action to the respective objects is required.
        """
        
        # Clean-up old pods
        cleanup_pods()
        # Initialize infrastructure-related dicts
        self.nodes, self.type_list = create_node_type_dict()
        self.constraints = get_description_constraints()

        # logger.info(f'self.type_list {self.type_list}')
        # logger.info(f'self.constraints {self.constraints}')

        self.nodes['kubernetes'] = get_k8s_nodes()
        self.nodes['mlsysops']['generic'] = {}

        for type in self.nodes['mlsysops']:
            self.nodes['mlsysops'][type] = get_mls_nodes('mlsysopsnodes', type)
        
        # Create fluidity monitor task and insert it to the list
        self._system_monitor_task = FluidityMonitor(self.notification_queue)
        asyncio.create_task(self._system_monitor_task.run())
        self.__app_handler_task = asyncio.create_task(self._app_handler())
        self.mls_inbound_monitor_task = asyncio.create_task(self._mls_inbound_monitor())
        # Start application description watcher
        control_task = asyncio.create_task(self.watch_app())
        await control_task

    async def watch_app(self):
        """MLSysOpsApp controller.
        
        Creates watcher for fluidityapps resources.
        """

        crd_plural = 'mlsysopsapps'
        resource_description = 'CRD'
        
        try:
            co_api = kubernetes_asyncio.client.CustomObjectsApi()
            logger.info(f'resource_description {resource_description}, crd_plural {crd_plural}')
            list_func = lambda **kwargs: co_api.list_namespaced_custom_object(
                group=API_GROUP,
                version=VERSION,
                namespace=cluster_config.NAMESPACE,
                plural=crd_plural,
                **kwargs
            ) 
            watcher_obj = watcher.ResourceWatcher(
                list_func=list_func,
                resource_description=resource_description,
                # This notification queue is internal (used only for Fluidity)
                notification_queue = self.notification_queue,
                crd_plural=crd_plural
            )

            # Run watcher inside a cancellable task
            watcher_task = asyncio.create_task(watcher_obj.run())
            await watcher_task
        except Exception as e:
            logger.error('Unexpected exception encountered: %s', e)
        except asyncio.CancelledError:
            logger.info("Watcher task cancelled cleanly.")

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
                # logger.debug('App handler received %s', req['operation'])
                plan_uid = None
                agent_msg = {}
                status = None
                comp_dict = None
                uid = None
                spec = None
                origin = req.get("origin")
                payload = req.get("payload", None)
                if not payload:
                    continue

                name = payload.get("name", None)
                if not name:
                    continue
                
                # logger.debug(f'origin is {origin}')
                
                # From internal Fluidity watchers
                if origin == 'internal':
                    uid = payload.get("uid", None)
                    spec = payload.get("spec", None)
                    resource = payload.get("resource", None)
                # From spade agent
                elif origin == 'spade':
                    plan = payload.get("deployment_plan", None)
                    plan_uid = payload.get("plan_uid")

                    if not plan or list(plan.keys()) == ['initial_plan']:
                        logger.info('Plan does not have the correct format.')
                        continue

                    initial_plan = plan.get("initial_plan", None)
                    if initial_plan == None:
                        logger.info('initial_plan is None. Going to continue')
                        continue

                    if name in self.apps_dict:
                        uid = self.apps_dict[name]['uid']
                        spec = self.apps_dict[name]['spec']

                match req['operation']:
                    case 'ADDED':
                        match resource:
                            case 'mlsysopsapps':
                                await self._handle_add_app(name, spec, uid)
                                event = MessageEvents.APP_CREATED.value
                            case 'mlsysopsnodes' | 'Node':
                                # Add the respective entry
                                update_resource(name, spec, resource, self.nodes)
                            case 'Pod' | 'mlsysopsclusters':
                                pass
                            case _:
                                logger.error(f"Caught unknown event (ignored)")
                                continue
                    case 'MODIFIED':
                        match resource:
                            case 'mlsysopsapps':
                                res, comp_dict = await self._handle_upd_app(name, spec)
                                if res:
                                    status = Status.COMPLETED.value
                                else:
                                    status = Status.FAILED.value

                                event = MessageEvents.APP_UPDATED.value
                            case 'mlsysopsnodes' | 'Node':
                                # Add the respective entry
                                update_resource(name, spec, resource, self.nodes)
                            case 'Pod' | 'mlsysopsclusters':
                                pass
                            case _:
                                logger.error(f"Caught unknown event (ignored)")
                                continue
                    case 'DELETED':
                        match resource:
                            case 'mlsysopsapps':
                                res = await self._handle_rm_app(name, spec)
                                if res:
                                    status = Status.COMPLETED.value
                                else:
                                    status = Status.FAILED.value

                                event = MessageEvents.APP_DELETED.value
                            case 'mlsysopsnodes' | 'Node':
                                # Add the respective entry
                                delete_resource(name, spec, resource, self.nodes)
                            case 'Pod' | 'mlsysopsclusters':
                                pass
                            case _:
                                logger.error(f"Caught unknown event (ignored)")
                                continue
                    case MessageEvents.PLAN_SUBMITTED.value:

                        if not plan_uid:
                            logger.error(f"Plan submitted without a plan uid, ignoring.")
                            continue

                        if initial_plan:
                            plan.pop('initial_plan')

                            for comp_name in plan:
                                if comp_name not in self.apps_dict[name]['components']:
                                    logger.error(f"Component {comp_name} not in internal app structure. Ignoring")
                                    continue

                                comp_spec = self.apps_dict[name]['components'][comp_name]
                                for action_entry in plan[comp_name]:
                                    if action_entry['action'] != 'deploy':
                                        logger.error('Received action != deploy, ignoring.')
                                        continue

                                    # Validate new host
                                    if not validate_host(comp_spec['pod_template'], comp_spec, action_entry['host'], self.nodes):
                                        logger.error(f"Host {action_entry['host']} did not pass eligibility check")
                                        status = Status.FAILED.value
                                        break
                                        
                                    action_entry['status'] = 'PENDING'
                            
                            # if status is set to failed
                            if status:
                                comp_dict = {}
                            else:
                                logger.info('Created plan %s', plan)
                                self.apps_dict[name]['curr_plan']['curr_deployment'] = plan

                                deployment, comp_dict = deploy_app_pods_and_configs(self.apps_dict[name], self.nodes, plan_uid)
                                
                                if deployment:
                                    status = Status.COMPLETED.value                                
                                    await self.update_internal_structures(name)

                                    if not self.apps_dict[name]['monitor_started']:
                                        start_monitor = await self.start_monitor(name)

                                        if start_monitor:
                                            self.apps_dict[name]['monitor_started'] = True
                                        else:
                                            status = Status.FAILED.value
                                else:
                                    logger.error('Initial deployment failed.')
                                    status = Status.FAILED.value
                        else:
                            # logger.debug('Received new plan request %s', plan)
                            # logger.debug('curr plan %s', self.apps_dict[name]['curr_plan']['curr_deployment'])
                            # Extra check so that no adaptation is made if the initial plan is not executed
                            # for all app components 
                            initial_deployment_pending = False

                            for comp_name in self.apps_dict[name]['components']:
                                comp_spec = self.apps_dict[name]['components'][comp_name]

                                if 'hosts' not in comp_spec or comp_spec['hosts'] == []:
                                    initial_deployment_pending = True
                                    break
                            
                            if initial_deployment_pending:
                                logger.info('Initial deployment not executed for all components - ignoring')
                                status = Status.FAILED.value
                            else:
                                plan.pop('initial_plan')
                                self.apps_dict[name]['curr_plan']['curr_deployment'] = plan

                                res, comp_dict = await self._handle_upd_app(name, spec, plan_uid)
                                if res:
                                    status = Status.COMPLETED.value  
                                else:
                                    status = Status.FAILED.value

                        # This event will include one or more entries that specify individual events
                        # for each aspect of the produced plan
                        event = MessageEvents.PLAN_EXECUTED.value
                        logger.test(f"|2| Fluidity executed planuid:{plan_uid} with status:{status}")
                    case _:
                        logger.info('AppHandler: No event in notification_queue (ignored).')
                        continue
                # If app desc event or spade plan request, update the reply to be sent
                if resource == 'mlsysopsapps' or origin == 'spade':
                    agent_msg = create_msg(name, event, app_spec=spec, status=status,
                                           plan_uid=plan_uid, app_uid=uid, comp_dict=comp_dict)  
                # Else if a normal event for the rest CRs or node/pods received, forward message to spade.
                else:
                    agent_msg = req
                await self.mls_outbound_queue.put(agent_msg)
            except Exception as e:
                logger.exception("Error handling app request: %s", e)

    async def _handle_add_app(self, app_name, app_spec, app_uid):
        """Handle the deployment request of a new application.

        Args:
            app_name (str): The name of the application.
            app_spec (dict): The specification of the application.
            app_uid (str): The unique identifier of the application.
        """
        app_dict = copy.deepcopy(FluidityAppInfoDict)
        app_dict['name'] = app_name
        app_dict['uid'] = app_uid
        app_dict['spec'] = app_spec
        app_dict['monitor_started'] = False
        
        tmp_cluster_id = None
        if 'cluster_placement' in app_spec:
            logger.info('Parsing cluster_placement')
            if 'cluster_id' in app_spec['cluster_placement']:
                # Selecting the first cluster
                tmp_cluster_id = app_spec['cluster_placement']['cluster_id'][0]
            else:
                logger.error('No cluster_id found in app description.')

        logger.debug('App %s has required cluster_id set to: %s', app_name, tmp_cluster_id)
        
        # Iterate over components and populate the various data structures
        for component in app_spec['components']:
            #: dict: Extended component spec, with FluidityCompInfoDict fields
            comp_spec = copy.deepcopy(FluidityCompInfoDict)
            comp_spec['spec'] = copy.deepcopy(component)
            comp_spec['name'] = component['metadata']['name']

            if 'external_access' in component:
                comp_spec['external_access'] = component['external_access']
            else:
                comp_spec['external_access'] = False

            if 'uid' in component['metadata']:
                comp_spec['uid'] = component['metadata']['uid']

            if tmp_cluster_id != None:
                comp_spec['cluster_id'] = tmp_cluster_id
            
            # Add component to curr_deployment internal structure
            app_dict['curr_plan']['curr_deployment'][comp_spec['name']] = []
            # Update the way that this template is created (without reading a file)
            comp_spec['pod_template'] = create_pod_manifest(comp_spec)
            comp_spec['placement'] = []

            if 'node_placement' in component:
                if 'labels' in component['node_placement']:
                    comp_spec['labels'] = component['node_placement']['labels']

                if 'mobile' in component['node_placement'] and component['node_placement']['mobile'] == True:
                    comp_spec['mobile'] = True

                if 'continuum_layer' in component['node_placement']:
                    for layer in component['node_placement']['continuum_layer']:
                        update_comp_type(app_dict, comp_spec, layer)
            
            if 'qos_metrics' in component:
                comp_spec['qos_metrics'] = component['qos_metrics']

            # Retrieve computing resource requests/limits for Pod containers
            pod_spec = comp_spec['spec']
            for container in pod_spec['containers']:
                if 'platform_requirements' not in container:
                    continue

                if 'cpu' in container['platform_requirements']:
                    if 'requests' in container['platform_requirements']['cpu']:
                        cpu = float(parse_quantity(container['platform_requirements']['cpu']['requests']))
                        comp_spec['resources_requests']['cpu'] += cpu

                    if 'limits' in container['platform_requirements']['cpu']:
                        cpu = float(parse_quantity(container['platform_requirements']['cpu']['limits']))
                        comp_spec['resources_limits']['cpu'] += cpu

                if 'memory' in container['platform_requirements']:
                    if 'requests' in container['platform_requirements']['memory']:
                        memory = float(parse_quantity(container['platform_requirements']['memory']['requests']))
                        comp_spec['resources_requests']['memory'] += memory

                    if 'limits' in container['platform_requirements']['memory']:
                        memory = float(parse_quantity(container['platform_requirements']['memory']['limits']))
                        comp_spec['resources_limits']['memory'] += memory    
                    
            # If limits < requests, limits = requests
            if comp_spec['resources_limits']['cpu'] < comp_spec['resources_requests']['cpu']:
                comp_spec['resources_limits']['cpu'] = comp_spec['resources_requests']['cpu']

            if comp_spec['resources_limits']['memory'] < comp_spec['resources_requests']['memory']:
                comp_spec['resources_limits']['memory'] = comp_spec['resources_requests']['memory']

            # Add component specification to 'components' dict for fast lookups
            app_dict['components'][comp_spec['name']] = comp_spec
            

        # Get I/O component relations and create service manifests/objects
        for comp_name in app_dict['components']:
            comp_spec = app_dict['components'][comp_name]
            # Create Service manifest (dict) for service-providing components
            pod_template = comp_spec['spec']
            proto = None
            ports = None

            for container in pod_template['containers']:
                if 'ports' not in container:
                    continue

                ports = container['ports']

                for port in ports:
                    svc_port = port['container_port']
                    logger.info('Service port %s', svc_port)

                    if 'protocol' in port:
                        proto = port['protocol']
                    # NOTE: We assume a single exposed service port
                    break
                # NOTE: We assume single-container Pods
                break

            if ports != None and has_egress_relation(app_spec, comp_name):
                logger.info(f'Creating service for {comp_name}')
                svc = create_svc_manifest(app_name, app_uid, comp_name, svc_port, proto, comp_spec['external_access'])
                obj = create_svc_object(app_name, app_uid, comp_name, svc_port, proto, comp_spec['external_access'])

                comp_spec['svc_manifest'] = svc
                comp_spec['svc_object'] = obj
                comp_spec['svc_port'] = svc_port

                svc_obj = create_svc(comp_spec['svc_manifest'])
                if svc_obj is None:
                    logger.error('Failed to create svc with manifest %s', comp_spec['svc_manifest'])
                    return

                # Retrieve the assigned VIP
                comp_spec['svc_vip'] = svc_obj.spec.cluster_ip

        # Extend component Pod template manifests/objects with Fluidity-related info
        if 'component_interactions' in app_spec:

            for interaction in app_spec['component_interactions']:
                logger.info('Comp interactions %s', interaction)
                ingress_comp = None
                egress_comp = None

                if interaction['type'] == 'egress':
                    ingress_comp = interaction['component_name1']
                    egress_comp = interaction['component_name2']
                else:
                    ingress_comp = interaction['component_name2']
                    egress_comp = interaction['component_name1']

                if egress_comp is not None and ingress_comp is not None:
                    egress_spec = app_dict['components'][egress_comp]
                    comp_spec = app_dict['components'][ingress_comp]
                    svc_addr = '{}:{}'.format(egress_spec['svc_vip'], egress_spec['svc_port'])
                    # Add service VIP:port as parameter to container
                    extend_pod_env_template(comp_spec['pod_template'], svc_addr)

        for comp_name in app_dict['components']:
            comp_spec = app_dict['components'][comp_name]
            extend_pod_label_template(comp_spec['pod_template'], app_name,
                                    app_uid, comp_name)
            comp_spec['pod_object'] = create_pod_object(comp_spec['pod_template'])

        # Add new app to apps dictionary
        self.apps_dict[app_name] = app_dict
        
        for type in self.nodes['mlsysops']:
            nodelist = self.nodes['mlsysops'][type]
            #logger.info(f'Type: {type}, node list: {nodelist}')
            if type+'_comp_names' in app_dict:
                comp_names = app_dict[type+'_comp_names']
                #logger.info(f'comp_names {comp_names}')
            
    async def update_internal_structures(self, app_name):
        initial_plan = self.apps_dict[app_name]['curr_plan']['curr_deployment']

        for comp_name in initial_plan:
            logger.info('Initial deployment %s' % comp_name)
            comp_spec = self.apps_dict[app_name]['components'][comp_name]
            
            for entry in initial_plan[comp_name]:
                host_name = entry['host']
                update_comp_placement(self.nodes, comp_spec, host_name)
                logger.debug('placement: %s', comp_spec['placement'])

    async def start_monitor(self, app_name):
        # Create fluidityapp monitor thread and insert it to the list
        app_monitor = FluidityMonitor(self.notification_queue, self.apps_dict[app_name])
        
        logger.info(f"adding {app_name}")
        self._app_monitor_thr_dict[app_name] = {
            "app_monitor": app_monitor,
            "task": asyncio.create_task(app_monitor.run())
        }

        return True

    async def _handle_upd_app(self, app_name, new_app_spec, plan_uid):
        """Handle the update request for an existing application.

        Args:
            app_name (str): The name of the application.
            new_app_spec (dict): The (possibly) new application's specification.
        """
        app_copy = copy.deepcopy(self.apps_dict[app_name])
        # If app MODIFIED event captured.
        if new_app_spec != self.apps_dict[app_name]['spec']:
            # Prepare the deployment plan based on the permitted modifications
            # NOTE: In this version, change container img and Pod's resources/runtimeClassName
            # are supported.
            new_deployment_plan = {}
            new_deployment_plan['curr_deployment'] = {}
            res = translate_plan(new_deployment_plan,
                                 self.apps_dict[app_name]['components'],
                                 new_app_spec['components']
                                )
            if not res:
                logger.error(f'translate plan failed')
                # Revert to previous specs
                self.apps_dict[app_name] = app_copy
                return False, None
            # Update the app_spec and the deployment plan
            self.apps_dict[app_name]['spec'] = new_app_spec 
            logger.debug(f'change spec from description') # new_deployment_plan {new_deployment_plan}')
        else:
            logger.info('App not modified.')
            new_deployment_plan = self.apps_dict[app_name]['curr_plan']
            res = translate_plan(new_deployment_plan, self.apps_dict[app_name]['components'])
            if not res:
                logger.error(f'translate plan failed')
                # Revert to previous specs
                self.apps_dict[app_name] = app_copy
                return False, None
            logger.debug(f'change spec from policy')# new_deployment_plan {new_deployment_plan}')
            # We must do the same translation of the change spec plan

        plan_dict = {}

        for comp_name in new_deployment_plan['curr_deployment']:
            comp_spec = self.apps_dict[app_name]['components'][comp_name]
            updated_hosts = False
            plan_dict[comp_name] = copy.deepcopy(CompDict)
            # Get latest version of qos_metrics from app description.
            for component in new_app_spec['components']:
                if comp_name == component['metadata']['name'] and 'qos_metrics' in component:
                    comp_spec['qos_metrics'] = component['qos_metrics']
                    plan_dict[comp_name]['qos_metrics'] = component['qos_metrics']
                    break

            for entry in new_deployment_plan['curr_deployment'][comp_name]:
                action = entry['action']
                # For deploy or remove actions.
                host = None
                # For move action.
                move_src_host = None
                move_target_host = None

                if action == 'move':
                    move_src_host = entry['src_host']
                    move_target_host = entry['target_host']

                    logger.debug(f'Caught move cmd of {comp_name} from {move_src_host} to {move_target_host}')
                    logger.debug('comp_spec[hosts]: %s', comp_spec['hosts'])
                    
                    # Validate new host
                    if not validate_host(comp_spec['pod_template'], comp_spec, move_target_host, self.nodes):
                        logger.error(f"Host {move_target_host} did not pass eligibility check")
                        return False, {}

                    res = append_host_to_list({'host': move_src_host, 'status': 'INACTIVE'}, comp_spec['hosts'], remove=True)
                    if not res:
                        logger.error(f"Host {move_src_host} for removal of comp {comp_name} not found.")
                        return False, {}

                    append_host_to_list({'host': move_target_host, 'status': 'PENDING'}, comp_spec['hosts'])
                    updated_hosts = True                    
                elif action == 'deploy' or action == 'remove':
                    host = entry['host']
                    status = 'INACTIVE'
                    remove = True
                    if action == 'deploy':
                        status = 'PENDING'
                        remove = False
                        # Validate new host
                        if not validate_host(comp_spec['pod_template'], comp_spec, host, self.nodes):
                            logger.error(f"Host {host} did not pass eligibility check")
                            return False, {}

                    res = append_host_to_list({'host': host, 'status': status}, comp_spec['hosts'], remove=remove)
                    if not res:
                        logger.error(f"Host {host} for removal of comp {comp_name} not found.")
                        return False, {}

                    logger.debug(comp_spec['hosts'])
                    updated_hosts = True
                elif action == 'change_spec':
                    # logger.info('Will call change comp spec')
                    # NOTE: If change spec has been triggered via a policy, the policy should define the action that 
                    # contains the entire Pod specification, including new host, images, resources, runtime classes, etc.
                    # We also need
                    # Validate new spec
                    if not validate_host(entry['new_spec'], comp_spec, entry['host'], self.nodes):
                        logger.error(f"Host {entry['host']} did not pass eligibility check")
                        return False, {}

                    result, updated_spec = change_comp_spec(self.apps_dict[app_name], entry, comp_spec,
                                                            self.constraints, self.nodes, plan_uid)
                    
                    if not result:
                        logger.error('Pod spec modification failed')
                        self.apps_dict[app_name] = app_copy
                        return False, None

                    logger.info('Modified Pod specs accordingly.')
                    # logger.debug(f'Updated spec: {updated_spec}')

                    plan_dict[comp_name]['specs'][updated_spec['metadata']['name']] = create_pod_dict(
                                                                                      updated_spec['spec']['nodeName'],
                                                                                      MessageEvents.POD_MODIFIED.value,
                                                                                      {'comp_spec':entry['new_spec'],
                                                                                      'pod_spec': updated_spec}
                                                                                    ) 
                    # logger.debug(plan_dict[comp_name])
                else:
                    logger.error('Policy provided invalid action. Going to return.')
                    return
            
            if updated_hosts:
                self.apps_dict[app_name]['curr_plan']['curr_deployment'][comp_name] = comp_spec['hosts']
        
        # Create adjusted pod manifests
        new_pods = create_adjusted_pods_and_configs(self.apps_dict[app_name], self.nodes, plan_uid)
        if not new_pods:
            logger.error('create_adjusted_pods_and_configs failed.')
            self.apps_dict[app_name] = app_copy
            return False, None

        # Deploy new Pods
        deploy_status = deploy_new_pods(self.apps_dict[app_name], plan_dict)
        if not deploy_status:
            logger.error('deploy_new_pods failed.')
            self.apps_dict[app_name] = app_copy
            return False, None
        # Remove old Pods
        delete_status = check_for_hosts_to_delete(self.apps_dict[app_name], plan_dict)
        if not delete_status:
            logger.error('check_for_hosts_to_delete failed.')
            self.apps_dict[app_name] = app_copy
            return False, None

        # logger.debug(f'final dict is {plan_dict}')

        return True, plan_dict

    async def _handle_rm_app(self, app_name, app_spec):
        """Handle the removal request of an existing application.

        Args:
            app_name (str): The name of the application.
            app_spec (dict): The specification of the application.
        """
        if app_name not in self.apps_dict:
            logger.error(f'App {app_name} not in apps dict')
            return False
        
        try:
            app_dict = self.apps_dict[app_name]
            ret = delete_running_pods(self.apps_dict[app_name])

            if not ret:
                logger.error('Pod removal failed.')
                return False

            logger.info('Going to stop Monitor thread for app: %s', app_name)

            self._app_monitor_thr_dict[app_name]['task'].cancel()
                
            self.apps_dict[app_name].clear()
            del self.apps_dict[app_name]
        except Exception as e:
            logger.error(f"Error removing app: {e}")

        return True
        

async def main(inbound_queue=None, outbound_queue=None, cluster_description=None):
    """Main Controller loop."""
    # Configure logging
    # USE MLSYSOPS LOGGER

    # logger = logging.getLogger('')
    # formatter = logging.Formatter('%(asctime)s %(levelname)s '
    #                               '[%(filename)s] %(message)s ')
    # f_hdlr = logging.FileHandler('/var/tmp/cluster_agent_fluidity_mlsysops.log')
    # f_hdlr.setFormatter(formatter)
    # f_hdlr.setLevel(logging.INFO)
    # logger.addHandler(f_hdlr)
    # s_hdlr = logging.StreamHandler(sys.stdout)
    # s_hdlr.setFormatter(formatter)
    # s_hdlr.setLevel(logging.INFO)
    # logger.addHandler(s_hdlr)
    # logger.setLevel(logging.INFO)

    await kubernetes_asyncio.config.load_config()

    # Detect if controller is run within a Pod or outside
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()

    if 'MLSYSOPS_NAMESPACE' in os.environ:
        cluster_config.NAMESPACE = os.getenv['MLSYSOPS_NAMESPACE']
    else:
        cluster_config.NAMESPACE = 'mlsysops'

    if namespace_exists(cluster_config.NAMESPACE):
        logger.info('Namespace already exists.')
    else:
        logger.info('Namespace does not exist.')
        create_mls_namespace(cluster_config.NAMESPACE)    

    ensure_crds()
    hostname = os.getenv("NODE_NAME",socket.gethostname())
    working_dir = os.getcwd()

    if cluster_description:
        cluster_config.CLUSTER_ID = apply_cluster_description(file=cluster_description)
    else:
        cluster_config.CLUSTER_ID = apply_cluster_description(fpath=working_dir+"/descriptions/"+hostname+".yaml")

    if not cluster_config.CLUSTER_ID:
        logger.error("Error on applying cluster description")
        sys.exit(0)
    
    logger.info(f'Current namespace {cluster_config.NAMESPACE}')
    logger.info('Current cluster id: %s', cluster_config.CLUSTER_ID)
    
    controller = FluidityAppController(inbound_queue,outbound_queue)
    await controller.setup()

if __name__ == '__main__':
    asyncio.run(main())

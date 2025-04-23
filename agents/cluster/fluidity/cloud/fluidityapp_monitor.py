"""FluidityApp monitor module."""
from __future__ import print_function
import copy
# import json
import logging
# import os
# import queue
# import sys
import threading
import time
import asyncio
from fluidity_nodes import get_drones, get_dronestations, get_edgenodes, get_mobilenodes, get_cloudnodes, get_k8s_nodes, get_custom_nodes
from fluidityapp_util import FluidityNodeInfoDict
from kubernetes import client, config, watch
import fluidityapp_settings as fluidityapp_settings
logger = logging.getLogger(__name__)

DEPLOYED = 1
#deployment_url = "http://karmada.mlsysops.eu:1000/deployment"

async def send_global_app_deployment():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_app_removed', "gauge", DEPLOYED)

def find_updated_entries(new_list, old_list):
    """Checks for new/updated fluidity resources"""
    # TODO: Also add the case when an entry is removed from the new list, 
    # and should be added to the (removed) updated entries
    return [x for x in new_list if x not in old_list]

def find_new_nodes(new_list, old_list):
    """Checks for new nodes"""
    for entry1 in new_list:
        exists = False
        for entry2 in old_list:
            if entry1.metadata.name == entry2.metadata.name:
                exists = True
                break
        if exists == False:
            return True
    return False

def contains_type(app, type):
    for comp_name in app['components']:
            comp_spec = app['components'][comp_name]
            # Check for "type" placement components
            if comp_spec['placement'] == type:
                return True
    return False

class FluidityAppMonitor(threading.Thread):
    """Monitor the application execution."""

    def __init__(self, app, checker_sem, monitor_sem, nodes, notification_queue, context, system_metrics):
        threading.Thread.__init__(self)
        self.name = app['name']
        self.app = app
        # Replaced all the individual lists with a global dictionary
        self.nodes = nodes
        self.updated_nodes = copy.deepcopy(FluidityNodeInfoDict)
        self.block_monitor = monitor_sem
        self.block_checker = checker_sem
        self.notification_queue = notification_queue
        self.context = context
        self.system_metrics = system_metrics
        threading.Thread.deamon = True
        self.active = True
        self._resource_checker_thr = threading.Thread(name='resource-checker',
                                                      target=self._check_for_resources)
        config.load_kube_config()
        self.api = client.CoreV1Api()
    
    def _check_for_resources(self):
        """Check for resource changes and add resource updates to the notification_queue."""
        # NOTE: Currently working for edge,cloud components. May need to 
        # modify for drone, hybrid.
        logger.info('Resource checker thread started')
        # Used to store edgenodes that include the mobile node in their proximity
        while self.active is True:
            modified_resources = False
            self.block_checker.acquire()
            if not self.app:
                self.block_checker.release()
                #logger.info('Found app desc empty. Checker going to sleep')
                time.sleep(0.5)
                continue
            #logger.info('My plugin is %s', self.app['plugin_policy'])
            self.updated_nodes.clear()
            # This is to ensure that we will execute the analyze only if a relevant resource has been updated
            #contains_drone = contains_type(self.app, 'drone')
            contains_edge = contains_type(self.app, 'edge')
            contains_hybrid = contains_type(self.app, 'hybrid')
            contains_mobile = contains_type(self.app, 'mobile')
            contains_cloud = contains_type(self.app, 'cloud')
            asyncio.run(send_global_app_deployment())
            # Retrieve all telemetry data here.
            # NOTE: Here we assume that we always update the k8s node structure.
            # If a previous snapshot is needed, then do the same approach as
            # for the CRDs with modified resources and the policy should retrieve
            # the new k8snodes entries from its 'updated_nodes' parameter.
            self.nodes['k8snodes'] = get_k8s_nodes()
            # TODO: Check if a node becomes OFFLINE and if yes set the pod to INACTIVE
            # state in the current deployment.

            # If it contains the updated resource type (drone, hybrid, edge or cloud),
            # Update
            if contains_mobile:
                new_mobilenodes = get_custom_nodes('mlsysopsnodes', 'mobile')
                mobilenodes = find_updated_entries(new_mobilenodes, self.nodes['mobilenodes'])
                if mobilenodes != []:
                    self.updated_nodes['mobilenodes'] = mobilenodes
                    modified_resources = True
            if contains_cloud or contains_hybrid:
                new_cloudnodes = get_custom_nodes('mlsysopsnodes', 'cloud')
                cloudnodes = find_updated_entries(new_cloudnodes, self.nodes['cloudnodes'])
                if cloudnodes != []:
                    self.updated_nodes['cloudnodes'] = cloudnodes
                    modified_resources = True
            if contains_edge or contains_hybrid:
                new_edgenodes = get_custom_nodes('mlsysopsnodes', 'edge')
                edgenodes = find_updated_entries(new_edgenodes, self.nodes['edgenodes'])
                if edgenodes != []:
                    self.updated_nodes['edgenodes'] = edgenodes
                    modified_resources = True
            
            #if modified_resources:
            notify, self.context = self.app['plugin_policy'].analyze_status(self.app, self.nodes, self.context,
                                                                            self.system_metrics, self.updated_nodes,
                                                                            self.app['curr_plan']['curr_deployment'])
            for item in self.updated_nodes:
                self.nodes[item] = list(self.updated_nodes[item])
            if notify:
                resource_req = {
                    'name': self.name,
                    'type': 'resource-update',
                    'operation': 'MODIFIED'
                }
                #logger.info(proximity_list)
                logger.info('Monitor will publish %s' % resource_req)
                self.notification_queue.put(resource_req)

            self.block_checker.release()
            time.sleep(1.25)
        logger.info('Resource checker exiting.')

    def run(self):
        """Main thread function."""
        self._resource_checker_thr.start()
        logger.info('AppMonitor %s started', self.app['name'])
        while self.active is True:
            self.block_monitor.acquire()
            if self.app:
                for pod in self.app['pod_names']:
                    try:
                        resp = self.api.read_namespaced_pod(name=pod,
                                                            namespace='default')
                    except Exception as exc:
                        logger.error('Error reading pod %s', exc)
                        continue
                    if resp.status.phase == 'Failed':
                        pod_req = {
                            'type': 'pod-failure',
                            'operation': 'MODIFIED',
                            'pod-obj': pod
                        }
                        self.notification_queue.put(pod_req)
                    logger.info('%s status: %s', pod, resp.status.phase)
            self.block_monitor.release()
            time.sleep(15)
        logger.info('Monitor\'s run() exiting.')

    def stop(self):
        """Kill threads."""
        # if self.context['model_info'] is not None:
        #     logger.info('Monitors model %s', self.context['model_info'])
        #     # Sending the DELETE request
        #     print('Going to delete ' + self.context['model_info']['deployment_id'])
        #     try:
        #         response = requests.delete(deployment_url+"/"+self.context['model_info']['deployment_id'])
        #         # Checking the response
        #         if response.status_code == 200:
        #             print("Resource deleted successfully.")
        #         else:
        #             print(f"Failed to delete resource. Status code: {response.status_code}")
        #         # Verify that the removal was successful
        #         # response = requests.get(deployment_url+"/all")  #+deployment_id)
        #         # # Checking the response status code
        #         # if response.status_code == 200:
        #         #     # Parsing the JSON response
        #         #     data = response.json()
        #         #     print(json.dumps(data, sort_keys=True, indent=4))
        #         # else:
        #         #     print(f"Failed to retrieve data: {response.status_code}")
        #     except Exception as e:
        #         logger.error('Caught exception when deleting model %s', e)
        self.active = False
        self._resource_checker_thr.join()
        while self.is_alive():
            time.sleep(1)
        logger.info('AppMonitor stopped')

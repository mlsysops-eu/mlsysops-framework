"""Fluidity application-deployment helper functionality."""
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
import asyncio 
from kubernetes import client, utils #, config, watch
from kubernetes.utils.create_from_yaml import FailToCreateError
from kubernetes.client.rest import ApiException
# from ruamel.yaml import YAML
import fluidityapp_settings as fluidityapp_settings
from fluidity_objects_util import dict2yaml
from fluidityapp_config import send_notification_to_host, generate_all_policy_configs, generate_policy_configs, get_node_internal_ip, get_adhoc_info
from fluidityapp_scheduler import available_cloud_nodes, SCHEDULER_NAME
from fluidity_nodes import get_k8s_nodes, get_node_availability


logger = logging.getLogger(__name__)

PROXY_MODE = 'OFF'
PROXY_PORT = 9527
#RPI_PROXY_HOST = '172.22.171.13'
#EDGE1_HOST = '172.22.171.12'
#EDGE2_HOST = '172.22.171.11'

"""Message types to send for mobile node application-level redirection."""
info_adhoc = {
    'msg-type': 'adhoc-info',
    'ssid': '',
    'locus-ip': '',
    'pod-name': '',
    'pass': '..........'
}

info_disconnect = {
    'msg-type': 'disconnect',
}

info_connect_and_redirect = {
    'msg-type': 'connect-and-redirect',
    'redirect': 'true',
    'ssid': '',
    'locus-ip': '',
    'pod-name': '',
    'pod-ip': '',
    'pass': '..........'
}

info_start_redirect = {
    'msg-type': 'start-redirect',
    'pod-name': '',
    'pod-ip': '',
}

info_stop_redirect = {
    'msg-type': 'stop-redirect'
}



# model k3s cmd deployment and removal
MODEL_DEPLOYMENT_STARTED = 1
MODEL_REMOVAL_STARTED = 2

# App k3s cmd deployment and removal
CLASSIFIER_DEPLOYMENT_STARTED = 1
CLASSIFIER_REMOVAL_STARTED = 2
DETECTOR_DEPLOYMENT_STARTED = 3 
DETECTOR_REMOVAL_STARTED = 4
CAMERA_DEPLOYMENT_STARTED = 5
CAMERA_REMOVAL_STARTED = 6

# App/model deployment and removal completion
IDLE = 0
DEPLOYED = 1
REMOVED = 2

JETSON_HOSTS_CLASSIFIER = 100
VADER_HOSTS_CLASSIFIER = 101


async def send_global_app_deployment():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_app_removed', "gauge", DEPLOYED)

async def send_global_app_removal():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_app_removed', "gauge", REMOVED)

async def send_classifier_host_info(host):
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_classifier_host', "gauge", host)

async def send_classifier_app_deployment():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_classifier_app_deployed', "gauge", DEPLOYED)

async def send_classifier_app_removal(flag):
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_classifier_app_deployed', "gauge", REMOVED)
    if flag:
        await asyncio.sleep(2)
        fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_classifier_app_deployed', "gauge", DEPLOYED)

async def send_detector_app_deployment():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_detector_app_deployed', "gauge", DEPLOYED)

async def send_detector_app_removal():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_detector_app_deployed', "gauge", REMOVED)

async def send_camera_app_deployment():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_camera_app_deployed', "gauge", DEPLOYED)

async def send_camera_app_removal():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_camera_app_deployed', "gauge", REMOVED)

async def send_model_deployment():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_model_deployed', "gauge", DEPLOYED)

async def send_model_removal():
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_model_deployed', "gauge", REMOVED)

async def send_last_k3s_app_cmd(cmd):
    #fluidityapp_settings.mlsClient.pushLogInfo("Last command to Kubernetes: "+cmd)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_k3s_app_command', "gauge", cmd)
    await asyncio.sleep(2)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_k3s_app_command', "gauge", IDLE)

async def send_last_k3s_model_cmd(cmd):
    #fluidityapp_settings.mlsClient.pushLogInfo("Last command to Kubernetes: "+cmd)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_k3s_model_command', "gauge", cmd)
    await asyncio.sleep(2)
    fluidityapp_settings.mlsClient.pushMetric(f'uth_demo_fluidity_k3s_model_command', "gauge", IDLE)

def check_for_edge_host(name, edgenodes_list):
    #print('check for edge hosts')
    #print(name)
    #print(edgenodes_list)
    for entry in edgenodes_list:
        if entry['metadata']['name'] == name:
            return True
    return False

def get_random_key(length):
    """Get random key.

    Used to differentiate the different instances of the same component.
    """
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))


def apply_manifest_file(fpath):
    """Apply the manifest of a Kubernetes object from a file.

    Args:
        fpath (str): The path of the manifest file.
    """
    file_exists = os.path.exists(fpath)
    if not file_exists:
        logger.error('Manifest file not applied: does not exist (%s)', fpath)
        return None
    api_client = client.ApiClient()
    try:
        obj = utils.create_from_yaml(api_client, fpath, verbose=True)
        return obj
    except FailToCreateError as exc:
        logger.error('Manifest file not applied: %s', exc)
        return None


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
                'fluidity.gr/app': app_name,
                'fluidity.gr/component': component,
                'fluidity.gr/appUID': app_uid
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
                'fluidity.gr/app': app_name,
                'fluidity.gr/component': component
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
                'fluidity.gr/app': app_name,
                'fluidity.gr/component': component,
                'fluidity.gr/appUID': app_uid
            },
            name = component
            # name = '{}-svc'.format(component)
        ),
        spec = client.V1ServiceSpec(
            type = svc_type,
            ports = [client.V1ServicePort(
                port = port,
                protocol = proto
            )],
            selector = {
                'fluidity.gr/app': app_name,
                'fluidity.gr/component': component
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
            namespace='default')
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
                namespace='default')
            #print(resp)
        except ApiException as exc:
            logger.error('Failed to delete service: %s', exc)
    try:
        svc_obj = core_api.create_namespaced_service(body=svc_manifest,
                                                     namespace='default')
        #print(svc_obj)
        return svc_obj
    except ApiException as exc:
        logger.error('Failed to create service: %s', exc)
        return None

def create_pod_manifest(app_name, app_uid, comp_spec):
    """Create manifest for application component.
    Args:
        app_name (str): The Fluidity application name.
        app_uid (str): The Fluidity application unique identifier.
        comp_spec (obj): The Fluidity component specification.

    Returns:
        manifest (dict): The respective service manifest.
    """
    manifest = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {
            #'labels': {},
            'name': comp_spec['name']
        },
        'spec': {
            'containers': []
        }
    }
    #logger.info('app name: %s, app_uid: %s, comp_spec: %s', app_name, app_uid, comp_spec)
    if 'containers' in comp_spec['spec']:
        for container in comp_spec['spec']['containers']:
            # The containers field should be identical to the official kubernetes field.
            container['name'] = comp_spec['name']
            manifest['spec']['containers'].append(container)
            #logger.info('container %s', container)
            #sys.exit(0)
    if 'runtimeClassName' in comp_spec['spec']:
        manifest['spec']['runtimeClassName'] = comp_spec['spec']['runtimeClassName']
    if 'restartPolicy' in comp_spec['spec']:
        manifest['spec']['restartPolicy'] = comp_spec['spec']['restartPolicy']
    if 'hostNetwork' in comp_spec['spec']:
        manifest['spec']['hostNetwork'] = comp_spec['spec']['hostNetwork']
    #logger.info('final manifest: %s', manifest)        

    return manifest


def create_pod_object(manifest):
    """Create Pod object of component with Fluidity-related info.

    Args:
        manifest (dict): The Pod manifest (template).

    Returns:
        pod (obj): The respective V1Pod object.
    """
    #logger.info("MANIFEST WITHIN CREATE POD OBJECT %s", manifest['metadata'])
    pod = client.V1Pod(
        api_version = 'v1',
        kind = 'Pod',
        metadata = client.V1ObjectMeta(
            labels = manifest['metadata']['labels'],
            name = manifest['metadata']['name']
        ),
        spec = client.V1PodSpec(
            containers = manifest['spec']['containers'],
            # scheduler_name = manifest['spec']['schedulerName'],
            node_selector = manifest['spec']['nodeSelector'],
            # affinity = manifest['spec']['affinity']
        )
    )
    return pod


def extend_pod_label_template(manifest, app_name, app_uid, comp_name, placement):
    """Extend a component's Pod manifest template with Fluidity-related info.

    Inserts at Pod's metadata field the labels `fluidity.gr/app`,
    `fluidity.gr/appUID`, `fluidity.gr/component` and `fluidity.gr/componentUID`
    (completed later), and at spec field the `schedulerName` (not used) and
    `nodeAffinity` specifying the acceptable `fluidity.gr/node-type` based on
    the placement option and the identifier of the selected candidates.
    Args:
        manifest (dict): The existing Pod manifest (template) that is extended.
        app_name (str): The Fluidity application name.
        app_uid (str): The Fluidity application unique identifier.
        comp_name (str): The Fluidity component name.
        placement (str): The component placement option
         (drone, edge, hybrid, cloud).
    """
    # Add labels section in manifest, if it does not exist
    if 'labels' not in manifest['metadata']:
        manifest['metadata']['labels'] = {}
    labels = manifest['metadata']['labels']
    labels['fluidity.gr/app'] = app_name
    labels['fluidity.gr/appUID'] = app_uid
    labels['fluidity.gr/component'] = comp_name
    labels['fluidity.gr/componentUID'] = None # Inserted during Pod creation
    # Get the spec field
    pod_spec = manifest['spec']
    if 'nodeSelector' not in pod_spec:
        pod_spec['nodeSelector'] = {}
    #logger.info('*********Extended pod label manifest %s**********', manifest)

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
    #logger.info('extend_pod_env_template %s', pod_spec)
    if svc_addr != None:
        for container in pod_spec['containers']:
            if 'env' not in container:
                container['env'] = []
            container['env'].append({'name': 'SERVICE_ADDR', 'value': svc_addr})
    #logger.info('Extended pod env manifest %s', manifest)


def extend_pod_instance(manifest, pod_name, system_services, host_name=None):
    """Extend a component's instance Pod manifest with Fluidity-related info.

    Inserts at Pod's metadata field the instance's name and sets the label
    `fluidity.gr/componentUID` to that name/identifier. In case the component
    invokes a system service, it also sets the environment variables `APP_ID`
    and `COMP_ID` to the respective unique identifiers.

    Args:
        manifest (dict): The existing Pod manifest that is extended.
        pod_name (str): The Fluidity component instance name (unique identifier).
        system_services (bool): True if it invokes any system service,
         False otherwise.
    """
    #logger.info('EXTEND POD INSTANCE %s', manifest)
    if 'labels' not in manifest['metadata']:
        #logger.info('CREATING LABELS')
        manifest['metadata']['labels'] = {}
    manifest['metadata']['name'] = pod_name
    manifest['metadata']['labels']['fluidity.gr/componentUID'] = pod_name
    #logger.info(manifest)
    
    #print(manifest)

    #if 'volumes' not in manifest['spec'] and pod_name.find("image-checker") != -1:
    #    manifest['spec']['volumes'] = []
    #    manifest['spec']['volumes'].append({'name': 'image-checker-storage', 'path': '/var/tmp/app'})
    #    for container in manifest['spec']['containers']:
    #        if 'volumeMounts' not in container:
    #            container['volumeMounts'] = []
    #            container['volumeMounts'].append({'name': 'image-checker-storage', 'mountPath': '/app'})
    #resources:
    #  requests:
    #    memory: "52428800" #"50Mi"
    #    cpu: "0.5"
    #  limits:
    #    memory: "104857600" #"100Mi"
    #    cpu: "0.5"
    if host_name != None:
        for container in manifest['spec']['containers']:
            #logger.info('Will check if needed to reduce available Pod resources')
            if host_name == 'vm-virtual-machine':
                if 'resources' not in container:
                    container['resources'] = {
                        'requests': {
                            #'memory': "850Mi", #"52428800", #"50Mi"
                            'cpu': "1.25"
                        },
                        'limits': {
                            #'memory': "900Mi", #"104857600", #"100Mi"
                            'cpu': "1.25"
                        }
                    }
            else:
                pass
                #logger.info('Host is not the laptop. No action.')
    if system_services:
        # manifest['spec']['hostNetwork'] = 'True'
        manifest['spec']['hostNetwork'] = True
        app_uid = manifest['metadata']['labels']['fluidity.gr/appUID']
        for container in manifest['spec']['containers']:
            #if pod_name.find("image-checker") != -1:
            #    if 'volumeMounts' not in container:
            #        container['volumeMounts'] = []
            #        container['volumeMounts'].append({'name': 'imagechecker-storage', 'mountPath': '/app'})
            
            if 'env' not in container:
                container['env'] = []
            container['env'].append({'name': 'APP_ID', 'value': app_uid})
            container['env'].append({'name': 'COMP_ID', 'value': pod_name})


def pin_pod_instance(manifest, node_name):
    """Pin a component's instance Pod to a specific node."""
    manifest['spec']['nodeName'] = node_name


def set_pod_placement(manifest, node_type):
    """Set node-type of nodeSelector for hybrid components."""
    manifest['spec']['nodeSelector']['fluidity.gr/node-type'] = node_type


def add_related_edge_info(manifest, related_to):
    """Add the host of the interacting edge component instance."""
    manifest['metadata']['labels']['fluidity.gr/relatedEdgeHost'] = related_to

def destroy_wifi_connection(app, comp_name, edgenodes_list):
    logger.info('Going to destroy wifi connection')
    if PROXY_MODE == 'OFF' or not comp_name:
        logger.info('Proxy mode == OFF or comp name is void. Going to return.')
        return
    starting_time = time.perf_counter()
    comp_spec = app['components'][comp_name]
    # NOTE: Currently works for hosts of hybrid-to-mobile components.
    for host in comp_spec['hosts']:
        # Check for host status
        if host['status'] != 'INACTIVE':
            continue
        found = False
        for entry in edgenodes_list:
            if host['name'] == entry['metadata']['name']:
                found = True
                break
        if not found:
            return
        result = get_adhoc_info(host['name'], edgenodes_list)
        if result['direct-comm'] == True:
            mobile_comp_name = app['mobile_comp_names'][0]
            mobile_name_host = app['components'][mobile_comp_name]['hosts'][0]['name']
            mobile_host_ip = get_node_internal_ip(mobile_name_host)
            logger.info('Sending notific to disconnect')
            send_notification_to_host(mobile_host_ip, PROXY_PORT, info_disconnect)
    ending_time = time.perf_counter()
    diff = ending_time - starting_time


def initiate_wifi_connection(app, comp_name, edgenodes_list):
    #logger.info('Going to initiate wifi connection')
    if PROXY_MODE == 'OFF' or not comp_name:
        logger.info('Proxy mode == OFF or comp name is void. Going to return.')
        return
    starting_time = time.perf_counter()
    comp_spec = app['components'][comp_name]
    # NOTE: Currently works for hosts of hybrid-to-mobile components.
    for host in comp_spec['hosts']:
        # Check for host status
        if host['status'] == 'INACTIVE':
            for entry in edgenodes_list:
                if host['name'] == entry['metadata']['name']:
                #    logger.info('Old host was an edge node with redirection.')
                #    logger.info('Skipping early wifi connection.')
                    return
        elif host['status'] != 'PENDING':
            continue
        result = get_adhoc_info(host['name'], edgenodes_list)
        if result['direct-comm'] == True:
            mobile_comp_name = app['mobile_comp_names'][0]
            mobile_name_host = app['components'][mobile_comp_name]['hosts'][0]['name']
            mobile_host_ip = get_node_internal_ip(mobile_name_host)
            #logger.info('mobile host %s', mobile_host_ip)
            info_adhoc['ssid'] = result['ssid']
            info_adhoc['locus-ip'] = result['locus-ip']
            #info_adhoc['pod-name'] = app['pod_names'][-1]
            #logger.info('Sending notific to host')
            send_notification_to_host(mobile_host_ip, PROXY_PORT, info_adhoc)
    ending_time = time.perf_counter()
    diff = ending_time - starting_time
    #logger.info('Initiated wifi connection. Going to return.')

def create_adjusted_pods_and_configs(app):
    for comp_name in app['mobile_comp_names']:
        comp_spec = app['components'][comp_name]
        comp_cluster_id = comp_spec['cluster_id']
        pod_template = comp_spec['pod_template']
        for host in comp_spec['hosts']:
            if host['status'] != 'PENDING':
                continue
            pod_dict = copy.deepcopy(pod_template)
            uid = get_random_key(4)
            # uid = i
            pod_name = '{}-m-{}'.format(comp_name, uid)
            extend_pod_instance(pod_dict, pod_name, False)
            pin_pod_instance(pod_dict, host['name'])
            #set_pod_placement(pod_dict, 'mobile')
            comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})
            # pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
            # comp_spec['pod_fpaths'].append(pod_fpath)
            comp_spec['pod_names'].append(pod_name)
            # dict2yaml(pod_dict, pod_fpath) # just for visual debugging
            # Update status for the selected host
            host['status'] = 'ACTIVE'

    for comp_name in app['edge_comp_names']:
        comp_spec = app['components'][comp_name]
        comp_cluster_id = comp_spec['cluster_id']
        #system_services = bool('systemServices' in comp_spec)
        pod_template = comp_spec['pod_template']
        #edge_locs = comp_spec['staticLocations']
        loc_num = 0
        #for edge_loc in edge_locs:
        for host in comp_spec['hosts']:
            # Check for host status
            if host['status'] != 'PENDING':
                continue
            pod_dict = copy.deepcopy(pod_template)
            uid = get_random_key(4)
            pod_name = '{}-e-{}'.format(comp_name, uid)
            extend_pod_instance(pod_dict, pod_name, False)
            pin_pod_instance(pod_dict, host['name'])
            comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})
            # pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
            # comp_spec['pod_fpaths'].append(pod_fpath)
            comp_spec['pod_names'].append(pod_name)
            #dict2yaml(pod_dict, pod_fpath) # just for visual debugging
            # Update status for the selected host
            host['status'] = 'ACTIVE'
            # for entry in comp_spec['hosts']:
            #     if entry['name'] == host['name']:
            #         entry['status'] = 'ACTIVE'
            #         break
            #loc_num +=1
        #generate_policy_configs(comp_name, app)

    for comp_name in app['hybrid_mobile_comp_names']:
        comp_spec = app['components'][comp_name]
        logger.info('Create adjusted pods, Hybrid comp hosts: %s' % comp_spec['hosts'])
        comp_cluster_id = comp_spec['cluster_id']
        system_services = bool('systemServices' in comp_spec)
        pod_template = comp_spec['pod_template']
        for host in comp_spec['hosts']:
            # Check for host status
            #if host_name[1] == 'INACTIVE':
            #    # TODO: UNPIN POD INSTANCE
            if host['status'] != 'PENDING':
                continue
            # If the node is an edge node, notify to connecto to adhoc
            #if host['name'] != comp_spec['host_hybrid_cloud']:
            #    result = get_adhoc_info(host['name'], self.edgenodes_list)
            #    if result['direct-comm'] == True:
            #        mobile_comp_name = app['mobile_comp_names'][0]
            #        mobile_name_host = app['components'][mobile_comp_name]['hosts'][0]['name']
            #        mobile_host_ip = get_node_internal_ip(mobile_name_host)
            #        #logger.info('mobile host %s', mobile_host_ip)
            #        info_adhoc['ssid'] = result['ssid']
            #        info_adhoc['locus-ip'] = result['locus-ip']
            #        info_adhoc['pod-name'] = app['pod_names'][-1]
            #        send_notification_to_host(mobile_host_ip, PROXY_PORT, info_adhoc)
            pod_dict = copy.deepcopy(pod_template)
            uid = get_random_key(4)
            pod_name = '{}-hmc-{}'.format(comp_name, uid)
            # NOTE: The host name parameter in the function below is temporary for testing reasons.
            extend_pod_instance(pod_dict, pod_name, system_services, host['name'])
            pin_pod_instance(pod_dict, host['name'])
            # # NOTE:Check if set_pod_placement/add_related_edge_info needed
            # if host['name'] == comp_spec['host_hybrid_cloud']:
            #     set_pod_placement(pod_dict, 'cloud')
            # else:
            #     set_pod_placement(pod_dict, 'edge')
            comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})
            pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
            comp_spec['pod_fpaths'].append(pod_fpath)
            comp_spec['pod_names'].append(pod_name)
            dict2yaml(pod_dict, pod_fpath) # just for visual debugging
            logger.info(pod_dict)
            # Update status for the selected host
            host['status'] = 'ACTIVE'
        #generate_policy_configs(comp_name, app)

    # Max <cloudReplicas> Pods per cloud component
    for comp_name in app['cloud_comp_names']:
        comp_spec = app['components'][comp_name]
        comp_cluster_id = comp_spec['cluster_id']
        if 'cloudReplicas' in comp_spec:
            replicas = comp_spec['cloudReplicas']
        else:
            replicas = 1
        pod_template = comp_spec['pod_template']
        # for _ in range(replicas):
        for host in comp_spec['hosts']:
            if host['status'] != 'PENDING':
                continue
            pod_dict = copy.deepcopy(pod_template)
            uid = get_random_key(4)
            # uid = i
            pod_name = '{}-c-{}'.format(comp_name, uid)
            extend_pod_instance(pod_dict, pod_name, False)
            pin_pod_instance(pod_dict, host['name'])
            #set_pod_placement(pod_dict, 'cloud')
            comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})
            pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
            comp_spec['pod_fpaths'].append(pod_fpath)
            comp_spec['pod_names'].append(pod_name)
            dict2yaml(pod_dict, pod_fpath) # just for visual debugging
            # Update status for the selected host
            host['status'] = 'ACTIVE'

def delete_running_pods(app):
    logger.info('Deleting all running pods for app: %s', app['name'])
    api = client.CoreV1Api()
    for pod_name in app['pod_names']:
        if pod_name.startswith('classifier-app'):
            asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_REMOVAL_STARTED))
        elif pod_name.startswith('detector-app'):
            asyncio.run(send_last_k3s_app_cmd(DETECTOR_REMOVAL_STARTED))
        elif pod_name.startswith('camera-app'):
            asyncio.run(send_last_k3s_app_cmd(CAMERA_REMOVAL_STARTED))
        elif pod_name.startswith('uth-demo-ml-comp'):
            asyncio.run(send_last_k3s_model_cmd(MODEL_REMOVAL_STARTED))
        try:
            api.delete_namespaced_pod(name=pod_name, namespace='default',body=client.V1DeleteOptions(grace_period_seconds=0))
        except ApiException as exc:
            logger.error('Failed to delete Pod: %s', exc)
            return False
        if pod_name.startswith('classifier-app'):
            asyncio.run(send_classifier_app_removal(False))
        elif pod_name.startswith('detector-app'):
            asyncio.run(send_detector_app_removal())
        elif pod_name.startswith('camera-app'):
            asyncio.run(send_camera_app_removal())
        elif pod_name.startswith('uth-demo-ml-comp'):
            asyncio.run(send_model_removal())
    asyncio.run(send_global_app_removal())
    return True

def sync_remove_pod(pod_name, host_name):
    """
    The difference with the delete_pod is that the current function waits until the pod does not exist
    anymore (reading the pod fails). If the node is disconnected, it aborts.
    """
    api = client.CoreV1Api()
    try:
        api.delete_namespaced_pod(name=pod_name, namespace='default',body=client.V1DeleteOptions(grace_period_seconds=0))
    except ApiException as exc:
        logger.error('Failed to delete Pod: %s', exc)
        return False
    while True:
        time.sleep(1)
        nodes = get_k8s_nodes()
        if nodes == [] or get_node_availability(host_name, nodes) == False:
            break
        try:
            api.read_namespaced_pod(name=pod_name, namespace='default')
        except ApiException as exc:
            logger.info('Pod does not exist. %s', exc)
            break

def cleanup_pods():
    remove_process_list = []
    api = client.CoreV1Api()
    try:
        pods = api.list_namespaced_pod(namespace='default')
    except ApiException as exc:
        logger.error('Failed to delete Pod: %s', exc)
        return False
    pod_list = pods.items
    # logger.info('IN CLEANUP')
    # logger.info(pods)
    # logger.info(pod_list)
    for pod in pod_list:
        #logger.info('Pod', pod)
        pod_name = pod.metadata.name
        labels = pod.metadata.labels
        if labels == None:
            continue
        host_name = pod.spec.node_name
        if 'fluidity.gr/app' in labels:
            logger.info('Deleting pod with name %s', pod_name)
            logger.info('labels %s', pod.metadata.labels)
            logger.info('Pod has fluidity.gr/app label.')
            temp_process = multiprocessing.Process(target=sync_remove_pod, args=(pod_name, host_name))
            remove_process_list.append(temp_process)
    
    for process in remove_process_list:
        logger.info('Starting removal process %s', process)
        process.start()
    
    for process in remove_process_list:
        logger.info('Waiting for removal process to terminate %s', process)
        process.join()
    return True

def check_for_hosts_to_delete(app, edgenodes_list, connection_init_thread=None, disconnection_thread=None):
    """Checks for unused pods and deletes them."""
    agent_msg = []
    queue_dict = {
        'event': "deleted",
        'payload': {
            'hostname': '',
            'component_name': ''
        }
    }
    for comp_name in app['mobile_comp_names']:
        comp_spec = app['components'][comp_name]
        hosts_to_del = []
        for host in comp_spec['hosts']:
            # Check for host status
            if host['status'] != 'INACTIVE':
                continue
            hosts_to_del.append(host)
            if 'uth-demo-ml-comp' in comp_name:
                asyncio.run(send_last_k3s_model_cmd(MODEL_REMOVAL_STARTED))
            elif 'classifier-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_REMOVAL_STARTED))
            elif 'detector-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(DETECTOR_REMOVAL_STARTED))
            elif 'camera-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CAMERA_REMOVAL_STARTED))
            #logger.info('Found host to be removed')
            for pod in comp_spec['pod_manifests']:
                pod_dict = pod['file']
                #logger.info('Pod dict is %s',pod_dict)
                #logger.info('nodeName:%s', pod_dict['spec']['nodeName'])
                #logger.info('host name is:%s',host['name'])
                if pod_dict['spec']['nodeName'] == host['name']:
                    pod_name = pod_dict['metadata']['name']
                    comp_spec['pod_names'].remove(pod_name)
                    curr_dict = copy.deepcopy(queue_dict)
                    curr_dict['payload']['hostname'] = pod_dict['spec']['nodeName']
                    curr_dict['payload']['component_name'] = pod_name
                    agent_msg.append(curr_dict)
                    resp = delete_pod(pod_name,app)
                    if resp == False:
                        return False
                    #logger.info('AFTER DELETE POD')
                    # maybe delete policy config for the respective node if needed
                    # generate_policy_configs(comp_name, app)
            # Delete pod manifest from components dict
            for entry in list(comp_spec['pod_manifests']):
                if entry['file']['spec']['nodeName'] == host['name']:
                    comp_spec['pod_manifests'].remove(entry)
        # Iterate and delete host dictionaries
        # with format: {'name':edge_loc['hosts']['name'],'status':edge_loc['hosts']['status']}
        for host in hosts_to_del:
            comp_spec['hosts'].remove(host)
    for comp_name in app['edge_comp_names']:
        comp_spec = app['components'][comp_name]
        #edge_locs = comp_spec['staticLocations']
        #for edge_loc in edge_locs:
        hosts_to_del = []
        for host in comp_spec['hosts']:
            # Check for host status
            if host['status'] != 'INACTIVE':
                continue
            hosts_to_del.append(host)
            if 'uth-demo-ml-comp' in comp_name:
                asyncio.run(send_last_k3s_model_cmd(MODEL_REMOVAL_STARTED))
            elif 'classifier-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_REMOVAL_STARTED))
            elif 'detector-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(DETECTOR_REMOVAL_STARTED))
            elif 'camera-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CAMERA_REMOVAL_STARTED))
            #logger.info('Found host to be removed')
            for pod in comp_spec['pod_manifests']:
                pod_dict = pod['file']
                #logger.info('Pod dict is %s',pod_dict)
                #logger.info('nodeName:%s', pod_dict['spec']['nodeName'])
                #logger.info('host name is:%s',host['name'])
                if pod_dict['spec']['nodeName'] == host['name']:
                    pod_name = pod_dict['metadata']['name']
                    # pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
                    # comp_spec['pod_fpaths'].remove(pod_fpath)
                    comp_spec['pod_names'].remove(pod_name)
                    #logger.info('GOING TO CALL DELETE POD')
                    #logger.info('pod_names:%s',comp_spec['pod_names'])
                    curr_dict = copy.deepcopy(queue_dict)
                    curr_dict['payload']['hostname'] = pod_dict['spec']['nodeName']
                    curr_dict['payload']['component_name'] = pod_name
                    agent_msg.append(curr_dict)
                    resp = delete_pod(pod_name,app)
                    if resp == False:
                        return False
                    #logger.info('AFTER DELETE POD')
                    # maybe delete policy config for the respective node if needed
                    # generate_policy_configs(comp_name, app)
            # Delete pod manifest from components dict
            for entry in list(comp_spec['pod_manifests']):
                if entry['file']['spec']['nodeName'] == host['name']:
                    comp_spec['pod_manifests'].remove(entry)
        # Iterate and delete host dictionaries
        # with format: {'name':edge_loc['hosts']['name'],'status':edge_loc['hosts']['status']}
        for host in hosts_to_del:
            #edge_loc['hosts'].remove(host)
            comp_spec['hosts'].remove(host)
    for comp_name in app['cloud_comp_names']:
        comp_spec = app['components'][comp_name]
        #edge_locs = comp_spec['staticLocations']
        #for edge_loc in edge_locs:
        hosts_to_del = []
        for host in comp_spec['hosts']:
            # Check for host status
            if host['status'] != 'INACTIVE':
                continue
            hosts_to_del.append(host)
            if 'uth-demo-ml-comp' in comp_name:
                asyncio.run(send_last_k3s_model_cmd(MODEL_REMOVAL_STARTED))
            elif 'classifier-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_REMOVAL_STARTED))
            elif 'detector-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(DETECTOR_REMOVAL_STARTED))
            elif 'camera-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CAMERA_REMOVAL_STARTED))
            #logger.info('Found host to be removed')
            for pod in comp_spec['pod_manifests']:
                pod_dict = pod['file']
                #logger.info('Pod dict is %s',pod_dict)
                #logger.info('nodeName:%s', pod_dict['spec']['nodeName'])
                #logger.info('host name is:%s',host['name'])
                if pod_dict['spec']['nodeName'] == host['name']:
                    pod_name = pod_dict['metadata']['name']
                    # pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
                    # comp_spec['pod_fpaths'].remove(pod_fpath)
                    comp_spec['pod_names'].remove(pod_name)
                    #logger.info('GOING TO CALL DELETE POD')
                    #logger.info('pod_names:%s',comp_spec['pod_names'])
                    curr_dict = copy.deepcopy(queue_dict)
                    curr_dict['payload']['hostname'] = pod_dict['spec']['nodeName']
                    curr_dict['payload']['component_name'] = pod_name
                    agent_msg.append(curr_dict)
                    resp = delete_pod(pod_name,app)
                    if resp == False:
                        return False
                    #logger.info('AFTER DELETE POD')
                    # maybe delete policy config for the respective node if needed
                    # generate_policy_configs(comp_name, app)
            # Delete pod manifest from components dict
            for entry in list(comp_spec['pod_manifests']):
                if entry['file']['spec']['nodeName'] == host['name']:
                    comp_spec['pod_manifests'].remove(entry)
        # Iterate and delete host dictionaries
        # with format: {'name':edge_loc['hosts']['name'],'status':edge_loc['hosts']['status']}
        for host in hosts_to_del:
            #edge_loc['hosts'].remove(host)
            comp_spec['hosts'].remove(host)
    for comp_name in app['hybrid_mobile_comp_names']:
        comp_spec = app['components'][comp_name]
        hosts_to_del = []
        for host in comp_spec['hosts']:
            # Check for host status
            if host['status'] != 'INACTIVE':
                continue
            hosts_to_del.append(host)
            if 'uth-demo-ml-comp' in comp_name:
                asyncio.run(send_last_k3s_model_cmd(MODEL_REMOVAL_STARTED))
            elif 'classifier-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_REMOVAL_STARTED))
            elif 'detector-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(DETECTOR_REMOVAL_STARTED))
            elif 'camera-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CAMERA_REMOVAL_STARTED))
            #logger.info('Found host to be removed')
            for pod in comp_spec['pod_manifests']:
                pod_dict = pod['file']
                #logger.info('Pod dict is %s',pod_dict)
                #logger.info('nodeName:%s', pod_dict['spec']['nodeName'])
                #logger.info('host name is:%s',host['name'])
                if pod_dict['spec']['nodeName'] == host['name']:
                    pod_name = pod_dict['metadata']['name']
                    pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
                    comp_spec['pod_fpaths'].remove(pod_fpath)
                    comp_spec['pod_names'].remove(pod_name)
                    #logger.info('GOING TO CALL DELETE POD')
                    #logger.info('pod_names:%s',comp_spec['pod_names'])
                    #if PROXY_MODE == 'ON':
                    #    fluidityapp_settings.teardown_rules_start = time.perf_counter()
                        # check if name belongs to edge node
                    #    result = check_for_edge_host(host['name'], edgenodes_list)
                        # if true, send notification to edge
                    #    if result == True:
                    #        mobile_comp_name = app['mobile_comp_names'][0]
                    #        logger.info('mobile comp: %s', mobile_comp_name)
                    #        mobile_name_host = app['components'][mobile_comp_name]['hosts'][0]['name']
                    #        mobile_host_ip = get_node_internal_ip(mobile_name_host)
                    #        logger.info('mobile host %s', mobile_host_ip)
                    #        edge_host_ip = get_node_internal_ip(host['name'])
                            #print('Removed edge1')
                            # Notify RPi
                    #        send_notification_to_host(mobile_host_ip, PROXY_PORT, info_stop_rpi)
                            # Notify edge node 1
                    #        send_notification_to_host(edge_host_ip, PROXY_PORT, info_stop_edge)
                    #    fluidityapp_settings.teardown_rules_end = time.perf_counter()
                    #    notific_diff = fluidityapp_settings.teardown_rules_end - fluidityapp_settings.teardown_rules_start
                    curr_dict = copy.deepcopy(queue_dict)
                    curr_dict['payload']['hostname'] = pod_dict['spec']['nodeName']
                    curr_dict['payload']['component_name'] = pod_name
                    agent_msg.append(curr_dict)
                    resp = delete_pod(pod_name,app)
                    if resp == False:
                        return False
                    #logger.info('AFTER DELETE POD')
                    # maybe delete policy config for the respective node if needed
                    # generate_policy_configs(comp_name, app)
            # Delete pod manifest from components dict
            for entry in list(comp_spec['pod_manifests']):
                if entry['file']['spec']['nodeName'] == host['name']:
                    comp_spec['pod_manifests'].remove(entry)
        # Iterate and delete host dictionaries
        # with format: {'name':edge_loc['hosts']['name'],'status':edge_loc['hosts']['status']}
        print('Hosts_to_del')
        print(hosts_to_del)
        previous_host_is_edge = False
        for host in hosts_to_del:
            comp_spec['hosts'].remove(host)
            if PROXY_MODE == 'OFF':
                continue
            if disconnection_thread != None:
                thread_join_start = time.perf_counter()
                disconnection_thread.join()
                thread_join_end = time.perf_counter()
            #fluidityapp_settings.timer_start = time.perf_counter()
            # check if name belongs to edge node
            result = get_adhoc_info(host['name'], edgenodes_list)
            # if true, send notification to edge
            if result['direct-comm'] == True:
                mobile_comp_name = app['mobile_comp_names'][0]
                #logger.info('mobile comp: %s', mobile_comp_name)
                mobile_name_host = app['components'][mobile_comp_name]['hosts'][0]['name']
                mobile_host_ip = get_node_internal_ip(mobile_name_host)
                #logger.info('mobile host %s', mobile_host_ip)
                #edge_host_ip = get_node_internal_ip(host['name'])
                #print('Removed edge1')
                # Notify RPi
                send_notification_to_host(mobile_host_ip, PROXY_PORT, info_stop_redirect)
                previous_host_is_edge = True
                # Notify edge node 1
                #send_notification_to_host(edge_host_ip, PROXY_PORT, info_stop_edge)
                # fluidityapp_settings.timer_end = time.perf_counter()
                # notific_diff = fluidityapp_settings.timer_end - fluidityapp_settings.timer_start
        print(comp_spec['hosts'])
        if PROXY_MODE == 'OFF':
            continue
        if connection_init_thread != None:
            thread_join_start = time.perf_counter()
            connection_init_thread.join()
            thread_join_end = time.perf_counter()
        #fluidityapp_settings.timer_start = time.perf_counter()
        result = get_adhoc_info(comp_spec['hosts'][0]['name'], edgenodes_list)
        if result['direct-comm'] == True:
            mobile_comp_name = app['mobile_comp_names'][0]
            #logger.info('mobile comp: %s', mobile_comp_name)
            mobile_name_host = app['components'][mobile_comp_name]['hosts'][0]['name']
            mobile_host_ip = get_node_internal_ip(mobile_name_host)
            #logger.info('mobile host %s', mobile_host_ip)
            #adhoc_struct = get_adhoc_info(comp_spec['hosts'][0]['name'], edgenodes_list)
            #if adhoc_struct['ssid'] == '':
            #    logger.error('Adhoc info not found for node: %s', comp_spec['hosts'][0])
            #    continue
            #logger.info('adhoc struct = %s', adhoc_struct)
            if previous_host_is_edge == True:
                info_connect_and_redirect['ssid'] = result['ssid']
                info_connect_and_redirect['locus-ip'] = result['locus-ip']
                info_connect_and_redirect['pod-name'] = app['pod_names'][-1]
                info_connect_and_redirect['pod-ip'] = comp_spec['current_pod_ip']
                send_notification_to_host(mobile_host_ip, PROXY_PORT, info_connect_and_redirect)
            else:
                info_start_redirect['pod-name'] = app['pod_names'][-1]
                info_start_redirect['pod-ip'] = comp_spec['current_pod_ip']
                send_notification_to_host(mobile_host_ip, PROXY_PORT, info_start_redirect)
            # fluidityapp_settings.timer_end = time.perf_counter()
            # setup_diff = fluidityapp_settings.timer_end - fluidityapp_settings.timer_start
    return True, agent_msg
                

def delete_pod(pod_name,app):
    logger.info('Deleting pod with name:%s',pod_name)
    #fluidityapp_settings.timer_start = time.perf_counter()
    api = client.CoreV1Api()
    nodes = get_k8s_nodes()
    try:
        # NOTE: If grace period is not zero and the host is offline, the pod will continue having Running status after deletion.
        api.delete_namespaced_pod(name=pod_name, namespace='default',body=client.V1DeleteOptions(grace_period_seconds=0))
        # fluidityapp_settings.timer_end = time.perf_counter()
        # diff = fluidityapp_settings.timer_end - fluidityapp_settings.timer_start
        # fluidityapp_settings.timer_start = time.perf_counter()
        app['total_pods'] -= 1
        app['pod_names'].remove(pod_name)
    except ApiException as exc:
        logger.error('Failed to delete Pod: %s', exc)
        #app['total_pods'] = 0
        #app['pod_names'] = []
        return False
    # Check until status is Terminating with sleep(0.05)
    # Also handle exception
    while True:
        try:
            resp = api.read_namespaced_pod(name=pod_name, namespace='default')
            logger.info(resp.status.phase)
            if resp.status.phase != "Running" or get_node_availability(resp.spec.node_name, nodes) == False:
                break
        except ApiException as exc:
            #logger.error('Failed to read pod: %s', exc)
            break
        time.sleep(0.05)
    logger.info('Deleted pod with name:%s',pod_name)
    if pod_name.startswith('classifier-app'):
        asyncio.run(send_classifier_app_removal(True))
    elif pod_name.startswith('detector-app'):
        asyncio.run(send_detector_app_removal())
    elif pod_name.startswith('camera-app'):
            asyncio.run(send_camera_app_removal())
    elif pod_name.startswith('uth-demo-ml-comp'):
        asyncio.run(send_model_removal())
    # fluidityapp_settings.timer_end = time.perf_counter()
    # status_diff = fluidityapp_settings.timer_end - fluidityapp_settings.timer_start
    return True

def deploy_new_pods(app):
    #logger.info('Deploy NEW Pods for components of app: %s', app['name'])
    api = client.CoreV1Api()
    nodes = get_k8s_nodes()
    #start = 0
    # List of dicts, one for each host containing the respective pod Spec
    # for the components deployed on that node.
    agent_msg = []
    queue_dict = {
        'event': "application_component_placed",
        'payload': {
            'hostname': '',
            'component_name': '',
            'comp_specs': [], # List of dicts
            'qos_metrics': [] # List of dicts
        }
    }

    for comp_name in app['mobile_comp_names']:
        comp_spec = app['components'][comp_name]
        for pod_dict in comp_spec['pod_manifests']:
            if pod_dict['status'] != 'PENDING':
                continue
            if 'uth-demo-ml-comp' in comp_name:
                asyncio.run(send_last_k3s_model_cmd(MODEL_DEPLOYMENT_STARTED))
            elif 'classifier-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_DEPLOYMENT_STARTED))
            elif 'detector-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(DETECTOR_DEPLOYMENT_STARTED))
            elif 'camera-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CAMERA_DEPLOYMENT_STARTED))
            curr_dict = copy.deepcopy(queue_dict)
            curr_dict['payload']['hostname'] = pod_dict['file']['spec']['nodeName']
            curr_dict['payload']['component_name'] = comp_name
            spec_entry = {
                'name': pod_dict['file']['metadata']['name'],
                'spec': pod_dict['file']
            }
            curr_dict['payload']['comp_specs'].append(spec_entry)
            curr_dict['payload']['qos_metrics'] = comp_spec['qos_metrics']
            agent_msg.append(curr_dict)
            try:
                api.create_namespaced_pod(body=pod_dict['file'], namespace='default')
                app['total_pods'] +=1
                app['pod_names'].append(pod_dict['file']['metadata']['name'])
                pod_dict['status'] = 'ACTIVE'
            except ApiException as exc:
                logger.error('Failed to create edge Pods: %s', exc)
                app['total_pods'] = 0
                app['pod_names'] = []
                return
    for comp_name in app['cloud_comp_names']:
        comp_spec = app['components'][comp_name]
        for pod_dict in comp_spec['pod_manifests']:
            if pod_dict['status'] != 'PENDING':
                continue
            if 'uth-demo-ml-comp' in comp_name:
                asyncio.run(send_last_k3s_model_cmd(MODEL_DEPLOYMENT_STARTED))
            elif 'classifier-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_DEPLOYMENT_STARTED))
            elif 'detector-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(DETECTOR_DEPLOYMENT_STARTED))
            elif 'camera-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CAMERA_DEPLOYMENT_STARTED))
            curr_dict = copy.deepcopy(queue_dict)
            curr_dict['payload']['hostname'] = pod_dict['file']['spec']['nodeName']
            curr_dict['payload']['component_name'] = comp_name
            spec_entry = {
                'name': pod_dict['file']['metadata']['name'],
                'spec': pod_dict['file']
            }
            curr_dict['payload']['comp_specs'].append(spec_entry)
            curr_dict['payload']['qos_metrics'] = comp_spec['qos_metrics']
            agent_msg.append(curr_dict)
            try:
                api.create_namespaced_pod(body=pod_dict['file'], namespace='default')
                app['total_pods'] +=1
                app['pod_names'].append(pod_dict['file']['metadata']['name'])
                pod_dict['status'] = 'ACTIVE'
            except ApiException as exc:
                logger.error('Failed to create edge Pods: %s', exc)
                app['total_pods'] = 0
                app['pod_names'] = []
                return
    for comp_name in app['edge_comp_names']:
        comp_spec = app['components'][comp_name]
        for pod_dict in comp_spec['pod_manifests']:
            if pod_dict['status'] != 'PENDING':
                continue
            if 'uth-demo-ml-comp' in comp_name:
                asyncio.run(send_last_k3s_model_cmd(MODEL_DEPLOYMENT_STARTED))
            elif 'classifier-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_DEPLOYMENT_STARTED))
            elif 'detector-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(DETECTOR_DEPLOYMENT_STARTED))
            elif 'camera-app' in comp_name:
                asyncio.run(send_last_k3s_app_cmd(CAMERA_DEPLOYMENT_STARTED))
            curr_dict = copy.deepcopy(queue_dict)
            curr_dict['payload']['hostname'] = pod_dict['file']['spec']['nodeName']
            curr_dict['payload']['component_name'] = comp_name
            spec_entry = {
                'name': pod_dict['file']['metadata']['name'],
                'spec': pod_dict['file']
            }
            curr_dict['payload']['comp_specs'].append(spec_entry)
            curr_dict['payload']['qos_metrics'] = comp_spec['qos_metrics']
            agent_msg.append(curr_dict)
            try:
                api.create_namespaced_pod(body=pod_dict['file'], namespace='default')
                app['total_pods'] +=1
                app['pod_names'].append(pod_dict['file']['metadata']['name'])
                pod_dict['status'] = 'ACTIVE'
            except ApiException as exc:
                logger.error('Failed to create edge Pods: %s', exc)
                app['total_pods'] = 0
                app['pod_names'] = []
                return
    # Used to just store the comp_spec to check the pod_ip
    # Outside the for loop. It is used only for the ImageChecker.
    # TODO: Find a more general solution for this functionality.
    temp_comp_spec = None
    for comp_name in app['hybrid_mobile_comp_names']:
        comp_spec = app['components'][comp_name]
        temp_comp_spec = comp_spec
        for pod_dict in comp_spec['pod_manifests']:
            if pod_dict['status'] != 'PENDING':
                continue
            curr_dict = copy.deepcopy(queue_dict)
            curr_dict['payload']['hostname'] = pod_dict['file']['spec']['nodeName']
            curr_dict['payload']['component_name'] = comp_name
            spec_entry = {
                'name': pod_dict['file']['metadata']['name'],
                'spec': pod_dict['file']
            }
            curr_dict['payload']['comp_specs'].append(spec_entry)
            curr_dict['payload']['qos_metrics'] = comp_spec['qos_metrics']
            agent_msg.append(curr_dict)
            try:
                #fluidityapp_settings.timer_start = time.perf_counter()
                api.create_namespaced_pod(body=pod_dict['file'], namespace='default')
                #fluidityapp_settings.timer_end = time.perf_counter()
                #elapsed = fluidityapp_settings.timer_end - fluidityapp_settings.timer_start
                
                #fluidityapp_settings.timer_start = time.perf_counter()
                app['total_pods'] +=1
                app['pod_names'].append(pod_dict['file']['metadata']['name'])
                pod_dict['status'] = 'ACTIVE'
            except ApiException as exc:
                logger.error('Failed to create edge Pods: %s', exc)
                app['total_pods'] = 0
                app['pod_names'] = []
                return
    # Wait for all pods to run
    logger.info('Waiting for all pods to have status running') 
    for pod_name in app['pod_names']:
        while True:
            try:
                resp = api.read_namespaced_pod(name=pod_name, namespace='default')
            except ApiException as exc:
                logger.error('Error reading pod %s', exc)
                break
            logger.info('host is %s', resp.spec.node_name)
            if resp.status.phase == "Running" and get_node_availability(resp.spec.node_name, nodes):
                # Also store the pod's ip address. Will be sent to the mobile node's
                # net proxy to be further forwarded to the other netproxy.
                if temp_comp_spec != None:
                    temp_comp_spec['current_pod_ip'] = resp.status.pod_ip
                # if temp_comp_spec['current_pod_ip'] == None:
                #     logger.error('Did not find the pod ip of imageChecker')
                # else:
                #     logger.info('Ip of image checker is %s' % temp_comp_spec['current_pod_ip'])
                if 'classifier-app' in pod_name:
                    asyncio.run(send_classifier_app_deployment())
                    if resp.spec.node_name == 'csl-jetson1':
                        asyncio.run(send_classifier_host_info(JETSON_HOSTS_CLASSIFIER))
                    elif resp.spec.node_name == 'csl-vader':
                        asyncio.run(send_classifier_host_info(VADER_HOSTS_CLASSIFIER))
                elif 'detector-app' in pod_name:
                    asyncio.run(send_detector_app_deployment())
                elif 'camera-app' in pod_name:
                    asyncio.run(send_camera_app_deployment())
                break
            elif get_node_availability(resp.spec.node_name, nodes) == False:
                break
            time.sleep(0.05)
    #logger.info('After pod deployment, the agent msg is: %s', agent_msg)
    return agent_msg

def check_violated_priority(high, low, priority_list):
    # Assuming single dependency per app 
    high_idx = priority_list.index(high)
    low_idx = priority_list.index(low)
    # logger.info('High idx %s', high_idx)
    # logger.info('Low idx %s', low_idx)
    if low_idx < high_idx:
        #logger.info('Going to rearrange elements')
        temp = priority_list[low_idx]
        priority_list[low_idx] = priority_list[high_idx]
        priority_list[high_idx] = temp

def reconfigure_deployment(app, spade_request):
    """Update Pod spec and policy configs for all selected component instances.

    Args:
        app (dict): The FluidityApp info dictionary.
        spade_request (list): Contains the dicts that correspond to the new
                              desired Pod specs.
    """
    # NOTE: There are possible improvements:
    # Check if Pod patch/update can be applied.
    # Patch updates only specified fields, while update requires the full spec.
    # For example, see container resizePolicy
    # We can patch the pod to change the image
    # Also we can change the resource requests and limits
    # Steps:
    # (1) Read the new pod Spec.
    # (2) Deploy the new Pod (with new uid following the comp name).
    # (3) Remove the old Pod.
    # (4) Update the Pod template, and pod name in the list of pod names.
    # Just for visualization, for each component we have the following:
    # 'event': "application_component_placed",
    # 'payload': {
    #     'hostname': '',
    #     'component_name': '',
    #     'comp_specs': [], # List of dicts
    #     'qos_metrics': [] # List of dicts
    # }
    for entry in spade_request:
        event = entry.get("event")
        payload = entry.get("payload")
        name = payload.get("component_name")
        if name not in app['components']:
            logger.error('Component %s does not belong to app component list. Continue...')
            continue
        specs_list = payload.get("comp_specs")
        for new_spec in specs_list:
            # NOTE: We assume that this name is the Pod's old name.
            # So we just need to create a new Pod name and once everything is ready,
            # we must again notify the node-level agent that the reconfigurations is
            # completed successfully.
            old_pod_name = new_spec['metadata']['name']
            old_uid = old_pod_name.rsplit("-", 1)[-1]
            logger.info('Old uid is %s', old_uid)
            # Optimization: In case we just patch the pod, we do not need a new uid, as
            # the name will remain the same.
            new_uid = get_random_key(4)
            while new_uid == old_uid:
                new_uid = get_random_key(4)
            logger.info('New uid is %s', new_uid)
            new_pod_name = new_uid.join(old_pod_name.rsplit(old_uid, 1))
            logger.info('new pod spec %s', new_spec)
            pod_dict = copy.deepcopy(new_spec)
            extend_pod_instance(pod_dict, new_pod_name, False)
            # Create new Pod
            try:
                api.create_namespaced_pod(body=pod_dict, namespace='default')
                app['total_pods'] +=1
            except ApiException as exc:
                logger.error('Failed to create edge Pods: %s', exc)
                app['total_pods'] = 0
                app['pod_names'] = []
                return
            # Wait until the Pod has status running
            while True:
                nodes = get_k8s_nodes()
                try:
                    resp = api.read_namespaced_pod(name=new_pod_name, namespace='default')
                except ApiException as exc:
                    logger.error('Error reading pod %s', exc)
                    break
                logger.info('Waiting for comp %s to start running on %s', new_pod_name, resp.spec.node_name)
                if resp.status.phase == "Running" and get_node_availability(resp.spec.node_name, nodes):
                    break
                elif get_node_availability(resp.spec.node_name, nodes) == False:
                    logger.error('Failed to get node availability. %s', resp.spec.node_name)
                    return False
                time.sleep(0.5)
            # Delete the old Pod.
            resp = delete_pod(old_pod_name, app)
            if resp == False:
                return False
            # Replace old pod name with a new one.
            comp_spec['pod_names'] = list(map(lambda x: new_pod_name if x == old_pod_name else x, comp_spec['pod_names']))
            comp_spec['pod_manifests'][0]['file'] = pod_dict
            comp_spec['pod_template'] = pod_dict
            logger.info('comp_spec[pod_names]: %s', comp_spec['pod_names'])
            logger.info('comp_spec[pod_manifests][0][file]: %s', comp_spec['pod_manifests'][0]['file'])
            logger.info('comp_spec[pod_template]: %s', comp_spec['pod_template'])
    
    return True

def deploy_app_pods_and_configs(app, initial_deployment):
    """Deploy Pods and policy configs for all selected component instances.

    Args:
        app (dict): The FluidityApp info dictionary.
    """
    # generate_all_policy_configs(app)
    logger.info('Deploy Pods for components of app: %s', app['name'])
    api = client.CoreV1Api()
    host_exists = False
    app['total_pods'] = 0
    app['pod_names'] = []
    priority_list = [key for key in app['components']]
    logger.info('Initial priority list %s', priority_list)
    #logger.info(app['components'])
    deployment_dependency = False
    for comp_name in app['components']:
        comp_spec = app['components'][comp_name]['spec']
        #logger.info(comp_spec)
        if 'DependsOn' in comp_spec:
            deployment_dependency = True
            low = comp_name
            high = comp_spec['DependsOn'][0]
            check_violated_priority(high, low, priority_list)
    logger.info('Final priority list %s', priority_list)
    #initial_deployment = priority_list

    # List of dicts, one for each host containing the respective pod Spec
    # for the components deployed on that node.
    agent_msg = []
    queue_dict = {
        'event': "application_component_placed",
        'payload': {
            'hostname': '',
            'component_name': '',
            'comp_specs': [], # List of dicts
            'qos_metrics': [] # List of dicts
        }
    }
    
    
    for priority_entry in priority_list:
        for comp_name in initial_deployment:
            if comp_name != priority_entry:
                continue
            pod_name = None
            logger.info('GOING TO DEPLOY: %s', comp_name)
            logger.info('Comp status: %s', initial_deployment[comp_name][0]['status'])
            if comp_name in app['hybrid_mobile_comp_names']:
                comp_spec = app['components'][comp_name]
                if  comp_spec['cluster_id'] != fluidityapp_settings.cluster_id:
                    logger.info('Found wrong cluster_id %s for comp %s (correct: %s). Ignoring ...', comp_spec['cluster_id'], comp_name, fluidityapp_settings.cluster_id)
                    continue
                if initial_deployment[comp_name][0]['status'] != 'PENDING':
                    continue
                logger.info('Valid cluster_id for comp %s. Deploying ...', comp_name)
                system_services = bool('systemServices' in comp_spec)
                pod_template = comp_spec['pod_template']
                for host in initial_deployment[comp_name]:
                    # Check for host status
                    #if host_name[1] == 'INACTIVE':
                    #    # TODO: UNPIN POD INSTANCE
                    if host['status'] != 'PENDING':
                        continue
                    if 'uth-demo-ml-comp' in comp_name:
                        asyncio.run(send_last_k3s_model_cmd(MODEL_DEPLOYMENT_STARTED))
                    elif 'classifier-app' in comp_name:
                        asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_DEPLOYMENT_STARTED))
                    elif 'detector-app' in comp_name:
                        asyncio.run(send_last_k3s_app_cmd(DETECTOR_DEPLOYMENT_STARTED))
                    elif 'camera-app' in comp_name:
                        asyncio.run(send_last_k3s_app_cmd(CAMERA_DEPLOYMENT_STARTED))
                    pod_dict = copy.deepcopy(pod_template)
                    uid = get_random_key(4)
                    pod_name = '{}-hmc-{}'.format(comp_name, uid)
                    extend_pod_instance(pod_dict, pod_name, system_services)
                    pin_pod_instance(pod_dict, host['name'])
                    # NOTE:Check if set_pod_placement/add_related_edge_info needed
                    # if host['name'] == comp_spec['host_hybrid_cloud']:
                    #     set_pod_placement(pod_dict, 'cloud')
                    # else:
                    #     set_pod_placement(pod_dict, 'edge')
                    comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})
                    #pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
                    #comp_spec['pod_fpaths'].append(pod_fpath)
                    comp_spec['pod_names'].append(pod_name)
                    #dict2yaml(pod_dict, pod_fpath) # just for visual debugging
                    # Update status for the selected host
                    host['status'] = 'ACTIVE'
                    curr_dict = copy.deepcopy(queue_dict)
                    curr_dict['payload']['hostname'] = pod_dict['spec']['nodeName']
                    curr_dict['payload']['component_name'] = comp_name
                    spec_entry = {
                        'name': pod_dict['metadata']['name'],
                        'spec': pod_dict
                    }
                    curr_dict['payload']['comp_specs'].append(spec_entry)
                    curr_dict['payload']['qos_metrics'] = comp_spec['qos_metrics']
                    agent_msg.append(curr_dict)
                comp_spec['hosts'] = copy.deepcopy(initial_deployment[comp_name])
                #generate_policy_configs(comp_name, app)
                for pod_dict in comp_spec['pod_manifests']:
                    if pod_dict['status'] != 'PENDING':
                        continue
                    try:
                        api.create_namespaced_pod(body=pod_dict['file'], namespace='default')
                        app['total_pods'] +=1
                        app['pod_names'].append(pod_dict['file']['metadata']['name'])
                        pod_dict['status'] = 'ACTIVE'
                        host_exists = True
                    except ApiException as exc:
                        logger.error('Failed to create edge Pods: %s', exc)
                        app['total_pods'] = 0
                        app['pod_names'] = []
                        return
            elif comp_name in app['mobile_comp_names']:
                comp_spec = app['components'][comp_name]
                if  comp_spec['cluster_id'] != fluidityapp_settings.cluster_id:
                    logger.info('Found wrong cluster_id %s for comp %s (correct: %s). Ignoring ...', comp_spec['cluster_id'], comp_name, fluidityapp_settings.cluster_id)
                    continue
                if initial_deployment[comp_name][0]['status'] != 'PENDING':
                    continue
                logger.info('Valid cluster_id for comp %s. Deploying ...', comp_name)
                #system_services = bool('systemServices' in comp_spec)
                pod_template = comp_spec['pod_template']
                #logger.info('pod_template %s', pod_template)
                pod_dict = copy.deepcopy(pod_template)
                uid = get_random_key(4)
                # uid = 0
                pod_name = '{}-{}'.format(comp_name, uid)
                extend_pod_instance(pod_dict, pod_name, False)
                # Retrieve the policy developer's desired host from the initial_deployment structure
                host_name = initial_deployment[comp_name][0]['name']
                if 'uth-demo-ml-comp' in comp_name:
                    asyncio.run(send_last_k3s_model_cmd(MODEL_DEPLOYMENT_STARTED))
                elif 'classifier-app' in comp_name:
                    asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_DEPLOYMENT_STARTED))
                elif 'detector-app' in comp_name:
                    asyncio.run(send_last_k3s_app_cmd(DETECTOR_DEPLOYMENT_STARTED))
                elif 'camera-app' in comp_name:
                    asyncio.run(send_last_k3s_app_cmd(CAMERA_DEPLOYMENT_STARTED))
                initial_deployment[comp_name][0]['status'] = 'ACTIVE'
                comp_spec['hosts'] = copy.deepcopy(initial_deployment[comp_name])
                pin_pod_instance(pod_dict, host_name)
                comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})
                #pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
                #comp_spec['pod_fpaths'].append(pod_fpath)
                comp_spec['pod_names'].append(pod_name)
                curr_dict = copy.deepcopy(queue_dict)
                curr_dict['payload']['hostname'] = pod_dict['spec']['nodeName']
                curr_dict['payload']['component_name'] = comp_name
                spec_entry = {
                    'name': pod_dict['metadata']['name'],
                    'spec': pod_dict
                }
                curr_dict['payload']['comp_specs'].append(spec_entry)
                curr_dict['payload']['qos_metrics'] = comp_spec['qos_metrics']
                agent_msg.append(curr_dict)
                #dict2yaml(pod_dict, pod_fpath) # just for visual debugging
                generate_policy_configs(comp_name, app)
                try:
                    api.create_namespaced_pod(body=pod_dict, namespace='default')
                    app['total_pods'] +=1
                    app['pod_names'].append(pod_name)
                    for entry in comp_spec['pod_manifests']:
                        if entry['file'] == pod_dict:
                            entry['status'] = 'ACTIVE'
                            host_exists = True
                except ApiException as exc:
                    logger.error('Failed to create drone Pods: %s', exc)
                    app['total_pods'] = 0
                    app['pod_names'] = []
                    return
            elif comp_name in app['cloud_comp_names']:
                comp_spec = app['components'][comp_name]
                if  comp_spec['cluster_id'] != fluidityapp_settings.cluster_id:
                    logger.info('Found wrong cluster_id %s for comp %s (correct: %s). Ignoring ...', comp_spec['cluster_id'], comp_name, fluidityapp_settings.cluster_id)
                    continue
                if initial_deployment[comp_name][0]['status'] != 'PENDING':
                    continue
                logger.info('Valid cluster_id for comp %s. Deploying ...', comp_name)
                #system_services = bool('systemServices' in comp_spec)
                pod_template = comp_spec['pod_template']
                #logger.info('pod_template %s', pod_template)
                pod_dict = copy.deepcopy(pod_template)
                uid = get_random_key(4)
                # uid = 0
                pod_name = '{}-{}'.format(comp_name, uid)
                extend_pod_instance(pod_dict, pod_name, False)
                if 'uth-demo-ml-comp' in comp_name:
                    asyncio.run(send_last_k3s_model_cmd(MODEL_DEPLOYMENT_STARTED))
                elif 'classifier-app' in comp_name:
                    asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_DEPLOYMENT_STARTED))
                elif 'detector-app' in comp_name:
                    asyncio.run(send_last_k3s_app_cmd(DETECTOR_DEPLOYMENT_STARTED))
                elif 'camera-app' in comp_name:
                    asyncio.run(send_last_k3s_app_cmd(CAMERA_DEPLOYMENT_STARTED))
                # Retrieve the policy developer's desired host from the initial_deployment structure
                host_name = initial_deployment[comp_name][0]['name']
                initial_deployment[comp_name][0]['status'] = 'ACTIVE'
                comp_spec['hosts'] = copy.deepcopy(initial_deployment[comp_name])
                pin_pod_instance(pod_dict, host_name)
                comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})
                #pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
                #comp_spec['pod_fpaths'].append(pod_fpath)
                comp_spec['pod_names'].append(pod_name)
                curr_dict = copy.deepcopy(queue_dict)
                curr_dict['payload']['hostname'] = pod_dict['spec']['nodeName']
                curr_dict['payload']['component_name'] = comp_name
                spec_entry = {
                    'name': pod_dict['metadata']['name'],
                    'spec': pod_dict
                }
                curr_dict['payload']['comp_specs'].append(spec_entry)
                curr_dict['payload']['qos_metrics'] = comp_spec['qos_metrics']
                agent_msg.append(curr_dict)
                #dict2yaml(pod_dict, pod_fpath) # just for visual debugging
                generate_policy_configs(comp_name, app)
                try:
                    api.create_namespaced_pod(body=pod_dict, namespace='default')
                    app['total_pods'] +=1
                    app['pod_names'].append(pod_name)
                    for entry in comp_spec['pod_manifests']:
                        if entry['file'] == pod_dict:
                            entry['status'] = 'ACTIVE'
                            host_exists = True
                except ApiException as exc:
                    logger.error('Failed to create drone Pods: %s', exc)
                    app['total_pods'] = 0
                    app['pod_names'] = []
                    return
            elif comp_name in app['edge_comp_names']:
                comp_spec = app['components'][comp_name]
                if  comp_spec['cluster_id'] != fluidityapp_settings.cluster_id:
                    logger.info('Found wrong cluster_id %s for comp %s (correct: %s). Ignoring ...', comp_spec['cluster_id'], comp_name, fluidityapp_settings.cluster_id)
                    continue
                if initial_deployment[comp_name][0]['status'] != 'PENDING':
                    continue
                logger.info('Valid cluster_id for comp %s. Deploying ...', comp_name)
                pod_template = comp_spec['pod_template']
                #logger.info('pod_template %s', pod_template)
                pod_dict = copy.deepcopy(pod_template)
                uid = get_random_key(4)
                # uid = 0
                pod_name = '{}-{}'.format(comp_name, uid)
                #logger.info('pod name: %s', pod_name)
                extend_pod_instance(pod_dict, pod_name, False)
                #logger.info('pod_dict %s', pod_dict)
                # Retrieve the policy developer's desired host from the initial_deployment structure
                host_name = initial_deployment[comp_name][0]['name']
                if 'uth-demo-ml-comp' in comp_name:
                    asyncio.run(send_last_k3s_model_cmd(MODEL_DEPLOYMENT_STARTED))
                elif 'classifier-app' in comp_name:
                    asyncio.run(send_last_k3s_app_cmd(CLASSIFIER_DEPLOYMENT_STARTED))
                elif 'detector-app' in comp_name:
                    asyncio.run(send_last_k3s_app_cmd(DETECTOR_DEPLOYMENT_STARTED))
                elif 'camera-app' in comp_name:
                    asyncio.run(send_last_k3s_app_cmd(CAMERA_DEPLOYMENT_STARTED))
                initial_deployment[comp_name][0]['status'] = 'ACTIVE'
                comp_spec['hosts'] = copy.deepcopy(initial_deployment[comp_name])
                pin_pod_instance(pod_dict, host_name)
                comp_spec['pod_manifests'].append({'file':pod_dict,'status':'PENDING'})
                # pod_fpath = '{}/pod-{}.yaml'.format(app['fpath'], pod_name)
                # comp_spec['pod_fpaths'].append(pod_fpath)
                comp_spec['pod_names'].append(pod_name)
                curr_dict = copy.deepcopy(queue_dict)
                curr_dict['payload']['hostname'] = pod_dict['spec']['nodeName']
                curr_dict['payload']['component_name'] = comp_name
                spec_entry = {
                    'name': pod_dict['metadata']['name'],
                    'spec': pod_dict
                }
                curr_dict['payload']['comp_specs'].append(spec_entry)
                curr_dict['payload']['qos_metrics'] = comp_spec['qos_metrics']
                agent_msg.append(curr_dict)
                # dict2yaml(pod_dict, pod_fpath) # just for visual debugging
                #generate_policy_configs(comp_name, app)
                try:
                    api.create_namespaced_pod(body=pod_dict, namespace='default')
                    app['total_pods'] +=1
                    app['pod_names'].append(pod_name)
                    for entry in comp_spec['pod_manifests']:
                        if entry['file'] == pod_dict:
                            entry['status'] = 'ACTIVE'
                            host_exists = True
                except ApiException as exc:
                    logger.error('Failed to create drone Pods: %s', exc)
                    app['total_pods'] = 0
                    app['pod_names'] = []
                    return
            else:
                logger.error('Component does not belong to any type.')
            if pod_name == None:
                logger.error('Pod name not created.')
                continue
            if deployment_dependency == True:
                while True:
                    nodes = get_k8s_nodes()
                    try:
                        resp = api.read_namespaced_pod(name=pod_name, namespace='default')
                    except ApiException as exc:
                        logger.error('Error reading pod %s', exc)
                        break
                    logger.info('Waiting for comp %s to start running on %s', pod_name, resp.spec.node_name)
                    if resp.status.phase == "Running" and get_node_availability(resp.spec.node_name, nodes):
                        break
                    elif get_node_availability(resp.spec.node_name, nodes) == False:
                        logger.error('Failed to get node availability. %s', resp.spec.node_name)
                        break
                    time.sleep(0.5)
    if not deployment_dependency:
        for pod_name in app['pod_names']:
            while True:
                nodes = get_k8s_nodes()
                try:
                    resp = api.read_namespaced_pod(name=pod_name, namespace='default')
                except ApiException as exc:
                    logger.error('Error reading pod %s', exc)
                    break
                logger.info('Waiting for comp %s to start running on %s', pod_name, resp.spec.node_name)
                if resp.status.phase == "Running" and get_node_availability(resp.spec.node_name, nodes):
                    if 'classifier-app' in pod_name:
                        asyncio.run(send_classifier_app_deployment())
                        if resp.spec.node_name == 'csl-jetson1':
                            asyncio.run(send_classifier_host_info(JETSON_HOSTS_CLASSIFIER))
                        elif resp.spec.node_name == 'csl-vader':
                            asyncio.run(send_classifier_host_info(VADER_HOSTS_CLASSIFIER))
                    elif 'detector-app' in pod_name:
                        asyncio.run(send_detector_app_deployment())
                    elif 'camera-app' in pod_name:
                        asyncio.run(send_camera_app_deployment())
                    elif 'uth-demo-ml-comp' in pod_name:
                        asyncio.run(send_model_deployment())
                    break
                elif get_node_availability(resp.spec.node_name, nodes) == False:
                    logger.error('Failed to get node availability. %s', resp.spec.node_name)
                    break
                time.sleep(0.5)
    logger.info('All pods to have status running')
    asyncio.run(send_global_app_deployment())
    return host_exists, agent_msg
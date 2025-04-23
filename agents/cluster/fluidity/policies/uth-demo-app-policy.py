"""Plugin module for custom policies - notify function."""
from __future__ import print_function
import pprint
import copy
import json
import logging
import os
import queue
import sys
import threading
import time
import random
import fluidityapp_settings
from geo_util import coords_to_shapely, is_in_cycle
from fluidityapp_settings import MOBILE_EDGE_PROXIMITY_RANGE
from fluidity_nodes import get_drones, get_dronestations, get_edgenodes, get_mobilenodes, update_app_resources, \
    get_node_availability
from fluidityapp_candidates import find_candidates_drone, find_candidates_edge, find_candidates_hybrid, \
    find_candidates_mobile
from fluidityapp_scheduler import select_hybrid_to_mobile_hosts, select_cloud_hosts, select_hosts, select_mobile_host
from fluidityapp_util import FluidityAppInfoDict, FluidityCompInfoDict, FluidityNodeInfoDict, FluidityPolicyAppInfoDict
from fluidityapp_util import HybridDroneInfoDict, HybridEdgeInfoDict, HybridMobileInfoDict  # , human_to_byte
from mlstelemetry import MLSTelemetry
from collections import deque
import requests
import socket

# model_url = "http://karmada.mlsysops.eu:1000/model"
# deployment_url = "http://karmada.mlsysops.eu:1000/deployment"
model_endpoint_url = "http://karmada.mlsysops.eu:10000/prediction"
# Get the hostname
hostname = socket.gethostname()

mlsClient = MLSTelemetry("fluidity_mechanism", "ubiwhere_policy")

logger = logging.getLogger(__name__)
initial_plan_executed = False
current_command = ''
curr_timestamp = None
prev_timestamp = None
jetson_bottom_latency_threshold = 30.5 # ms
jetson_top_latency_threshold = 40 # ms
vader_bottom_latency_threshold = 10 # ms
vader_top_latency_threshold = 21.1 # ms
qos_target = 40 # ms, lower than, equal to jetson bottom threshold
#latency_window = deque([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], maxlen=10)
latency_window = deque([0, 0, 0, 0, 0], maxlen=5)
#latency_window = deque([0, 0, 0], maxlen=3)
def update_comand(command):
    global current_command
    logger.info('in update_comand, cmd %s', command)
    logger.info('in update_comand, curr_cmd %s', current_command)
    current_command = command


def post_inference_request(endpoint, data):
    response = None
    # Send the POST request
    try:
        # response = requests.post(self.model_deployment['endpoint'], json=self.snapshot_history)
        response = requests.post(endpoint, json=data)
        # logger.info the response from the server
        logger.info("Response Status Code: %s", response.status_code)
        logger.info("Response JSON: %s", response.json())
    except requests.exceptions.RequestException as e:
        logger.error("An error occurred: %s", e)
        if response == None:
            return response
    logger.info('Inference response: %s', response.json())
    return response.json()

def get_model_kind(kind):
    """
    Get model with a specific kind
    """
    data = None
    # Sending the GET request
    try:
        response = requests.get(model_url + "/getkind/" + kind)
        # Checking the response status code
        if response.status_code == 200:
            # Parsing the JSON response
            data = response.json()
            logger.info(json.dumps(data, sort_keys=True, indent=4))
            # mymodel = data[0]
            # logger.info(mymodel["featurelist"])
        else:
            logger.error("Failed to retrieve data: %s", response.status_code)
    except requests.exceptions.RequestException as e:
        logger.error("An error occurred: %s", e)
    if data == None or data == []:
        return None
    # logger.info(data[0])
    return data[0]


def heuristic_func(model_input):
    logger.info(model_input)
    current_action = ''
    try:
        average_latency = model_input["obs_state"]["average_latency"]
        classifier_host = model_input["obs_state"]["classifier_host"]
        vader_power_value = model_input["obs_state"]["vader_power_value"]
        jetson_bottom_latency_threshold = model_input["obs_state"]["jetson_bottom_latency_threshold"]
        vader_top_latency_threshold = model_input["obs_state"]["vader_top_latency_threshold"]

        if classifier_host == 'csl-jetson1' and average_latency > jetson_bottom_latency_threshold: 
            logger.info('Host is jetson and latency > low_latency_threshold. cmd=Move to vader.')
            current_action = "move_classifier_to_vader"
        elif classifier_host == 'csl-jetson1' and average_latency < jetson_bottom_latency_threshold:
            logger.info('Host is jetson and latency < low_latency_threshold. cmd=No operation.')
        elif classifier_host == 'csl-vader' and average_latency < vader_top_latency_threshold and vader_power_value != None and vader_power_value == 0: 
            logger.info('Host is vader and high_latency_threshold > latency and VaderPowerMode=Low. cmd=Move to jetson.')
            # In this case it is safe to move to jetson since Jetson(H) and Vader(L)they have similar performance
            current_action = "move_classifier_to_jetson"
        elif classifier_host == 'csl-vader' and average_latency > vader_top_latency_threshold:
            logger.info('Host is vader and latency > low_latency_threshold. cmd=No operation.')
        logger.info("Returning action: %s", current_action)
        return current_action
    except Exception as e:
        logger.error('Caught exception %s on heuristic func', e)
    finally:
        return current_action

""" Plugin function to implement the initial deployment logic.
"""
def initial_plan(app_desc, nodes):
    # NOTE: The parsing of app_desc which the fluidity handles, should be moved here.
    logger.info('initial deployment phase')
    global initial_plan_executed
    global current_command
    global low_latency_threshold 
    global high_latency_threshold 
    global qos_target
    global counter
    #global desired_model
    counter = 0
    context = copy.deepcopy(FluidityPolicyAppInfoDict)
    
    
    context['nodes'] = dict(nodes)
    context['name'] = app_desc['name']
    context['spec'] = app_desc['spec']
    context['component_names'] = []
    
    plan = {}
    # plan['classifier-app'] = [{'name': 'csl-vader', 'status': 'PENDING'}]
    # plan['camera-app'] = [{'name': 'csl-rpi5-1', 'status': 'PENDING'}]
    # plan['detector-app'] = [{'name': 'csl-jetson1', 'status': 'PENDING'}]
    # desired_model = None
    # try:
    #     # Sending the GET request
    #     response = requests.get(model_url+"/getkind/prediction")
    #     # Checking the response status code
    #     if response.status_code == 200:
    #         # Parsing the JSON response
    #         data = response.json()
    #         print(json.dumps(data, sort_keys=True, indent=4))
    #         mymodel = data[0]
    #         print(mymodel["featurelist"])
    #         model_id = mymodel["modelid"]
    #         deployment = {
    #             "modelid": model_id,
    #             "ownerid": hostname,
    #             "placement": {
    #                 "clusterID": "uth-prod-cluster",
    #                 "node": hostname,
    #                 "continuum": False
    #             }
    #         }
    #         depl_response = requests.post(deployment_url+"/add", json=deployment)
    #         # Checking the response status code
    #         if depl_response.status_code == 201:  # 201 Created
    #             print("Successfully created:", depl_response.json())
    #             resp = depl_response.json()
    #             deployment_id = resp['deployment_id']
    #             deployment_status = resp['status']
    #             print(deployment_id)
    #             print(deployment_status)
                
    #             while deployment_status == 'waiting':
    #                 print('Status is '+ deployment_status)
    #                 time.sleep(1)
    #                 check_response = requests.get(deployment_url+"/all")  #+deployment_id)
    #                 # Checking the response status code
    #                 if check_response.status_code == 200:
    #                     # Parsing the JSON response
    #                     data = check_response.json()
    #                     #print(json.dumps(data, sort_keys=True, indent=4))
    #                     for entry in data:
    #                         if entry['deployment_id'] == deployment_id and entry['modelid'] == model_id \
    #                         and entry['ownerid'] == hostname:
    #                             print('Found desired model and deployment id', entry)
    #                             deployment_status = entry['status']
    #                             desired_model = entry
    #                     # mymodel = data[0]
    #                     # print(mymodel["featurelist"])
    #                     # model_id = mymodel["modelid"]
    #                 else:
    #                     print(f"Failed to retrieve data: {check_response.status_code}")
    #         else:
    #             print(f"Failed to create: {depl_response.status_code}")
    #     else:
    #         print(f"Failed to retrieve data: {response.status_code}")
    # except Exception as e:
    #     logger.error('Caught exception %s', e)
    
    # context['model_info'] = desired_model
    # if desired_model is not None:
    #     logger.info('model deployed successfully')
    # else:
    #     logger.error("Problem with model deployment")
    
    for component in app_desc['spec']['components']:
        comp_name = component['Component']['name']
        context['component_names'].append(comp_name)
        if 'QoS-Metrics' in component:
            for metric in component['QoS-Metrics']:
                if metric['ApplicationMetricID'] != 'classifier-latency':
                    continue
                qos_target = metric['target']
                logger.info('Found QoS metric %s with target %s', metric['ApplicationMetricID'], metric['target'])
        node_placement = component.get("nodePlacement")
        if node_placement:
            node_name = node_placement.get("node")
            if node_name:
                plan[comp_name] = [{'name': node_name, 'status': 'PENDING'}]
            elif comp_name == 'classifier-app':
                plan[comp_name] = [{'name': 'csl-jetson1', 'status': 'PENDING'}]
        else:
            logger.error('Did not find component-to-node mapping. Empty plan.')
            return {}, context
    return plan, context


def analyze_status(app_desc, nodes, context, system_metrics, updated_nodes, curr_deployment):
    global current_command
    global counter 
    global low_latency_threshold 
    global high_latency_threshold 
    global qos_target
    global curr_timestamp
    global prev_timestamp
    global latency_window
    #global desired_model
    # Low Power 0
    # High Power 1
    if counter == 0:
        counter += 1
        time.sleep(15)
    classifier_host = None
    for comp in curr_deployment:
        if comp == 'classifier-app':
            for comp_host in curr_deployment[comp]:
                if comp_host['status'] == 'ACTIVE':
                    classifier_host = comp_host['name']
                    break

    logger.info('Curr_deployment %s', curr_deployment)
    if classifier_host is None:
        logger.error("classifier_host is None")
        return False, context
    vader_power = mlsClient.get_metric_value_with_label(metric_name="node_agent_power_mode")
    if vader_power is None:
        logger.info("vader_power is None")
        vader_power_value = None
    else:
        vader_power_value = vader_power['value']
        logger.info('vader_power %s', vader_power_value)
        if vader_power_value == 1 and classifier_host == 'csl-vader':
            latency_window = deque([0] * latency_window.maxlen, maxlen=latency_window.maxlen)
            logger.info("VADER HOSTS CLASSIFIER AND HIGH POWER MODE DETECTED, deque  reset to zeros: %s", latency_window)
            return False, context
    # Get app metric
    logger.info('Current classifier host is %s', classifier_host)
    latency_dict = mlsClient.get_metric_value_with_label(metric_name="total_frame_latency", node_name=classifier_host)
    if latency_dict is None:
        logger.error("latency is None")
        mlsClient.pushMetric(f'uth_demo_fluidity_avg_latency', "gauge", 0)
        return False, context
    latency = latency_dict['value']
    logger.info('latency_dict: %s', latency_dict)
    latency_window.append(latency)
    if 0 in latency_window:
        logger.info('Waiting to fill the queue. Going to return.')
        return False, context
    
    logger.info('Current latency %s', latency)
    logger.info('latency_window %s', latency_window)
    average_latency = sum(latency_window) / len(latency_window)
    logger.info('Average window value %s', average_latency)
    # Get node power consumption mode for vader (low(L)/high(H))
    mlsClient.pushMetric(f'uth_demo_fluidity_avg_latency', "gauge", average_latency)
    # [avg_latency, classifier_host, vader_power_value, jetson_bottom_latency_threshold, vader_top_latency_threshold]
    # model_input = [average_latency, classifier_host, vader_power_value, jetson_bottom_latency_threshold, vader_top_latency_threshold]
    model_input = {
        "obs_state": {
            "average_latency": average_latency,
            "classifier_host": classifier_host,
            "vader_power_value": vader_power_value,
            "jetson_bottom_latency_threshold": jetson_bottom_latency_threshold,
            "vader_top_latency_threshold": vader_top_latency_threshold
        }
    }
    
    # ML MODEL INFERENCE INVOCATION
    model_response = None
    #if context['model_info'] is not None:
    
    try:
        response = requests.post(model_endpoint_url, json=model_input)
        # Print response
        logger.info("Status Code: %s", response.status_code)
        if response.status_code == 200:  # Success
            logger.info('ML BASED MODE')
            logger.info("Successfully asked for inference:", response.json())
            model_response = response.json()['action']
        else:
            logger.error(f"Failed to create: {response.status_code}")            
    except Exception as e:
        logger.error("Caught exception %s", e)
    # In case the model invocation fails or it does not exist
    if model_response is None or model_response == '':
        logger.info('Heuristic mode')
        model_response = heuristic_func(model_input)
    if model_response is not None and (model_response == "move_classifier_to_jetson" or model_response == "move_classifier_to_vader"):
        logger.info('Model response: %s', model_response)
        current_command = model_response
        # Empty the deque whenever we receive a command from the model
        latency_window = deque([0] * latency_window.maxlen, maxlen=latency_window.maxlen)
        logger.info("Deque reset to zeros: %s", latency_window)
        if current_command == "move_classifier_to_vader":
            logger.info('Host is jetson and latency > low_latency_threshold. cmd=Move to vader.')
        elif current_command == "move_classifier_to_jetson":
            logger.info('Host is vader and high_latency_threshold > latency > low_latency_threshold. cmd=Move to jetson.')
        return True, context
    else:
        logger.error('No response from model, going to return False')

    return False, context


def re_plan(old_app_desc, new_app_desc, context, curr_deployment):
    global current_command
    logger.info('Curr deployment: %s', curr_deployment)
    #classifier_host = curr_deployment['classifier-app'][0]['name']
    new_deployment = {
        'curr_deployment': {},
        'start_follow_tractor': False,
        'stop_follow_tractor': False,
        'enable_redirection': False,
        'disable_redirection': False
    }
    classifier_host = None
    for comp in curr_deployment:
        if comp == 'classifier-app':
            for comp_host in curr_deployment[comp]:
                if comp_host['status'] == 'ACTIVE':
                    classifier_host = comp_host['name']
                    break
    if classifier_host is not None:
        logger.info('classifier_host: %s', classifier_host)
    else:
        logger.error('Classifier host is None')
        return new_deployment, context

    cmd = current_command
    # Creation of the new_deployment as actions to be
    # provided to Fluidity's internal mechanism.
    logger.info('cmd is %s', cmd)
    if cmd == "NONE" or cmd == '':
        logger.info('Empty cmd.')
    else:
        mlsClient.pushLogInfo("Fluidity will execute command: " + cmd)
    #plan['classifier-app'] = [{'name': 'csl-vader', 'status': 'PENDING'}]
    for comp_name in curr_deployment:
        if comp_name == 'classifier-app':
            logger.info(comp_name)
            if 'move_classifier_to_vader' in cmd:
                new_deployment['curr_deployment'][comp_name] = {
                    'action': 'move',
                    'target_host': 'csl-vader',
                    'src_host': 'csl-jetson1'
                }
            elif 'move_classifier_to_jetson' in cmd:
                new_deployment['curr_deployment'][comp_name] = {
                    'action': 'move',
                    'target_host': 'csl-jetson1',
                    'src_host': 'csl-vader'
                }
    logger.info('Actions to be returned to Fluidity %s' % new_deployment)

    return new_deployment, context

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
    # Low Power 0
    # High Power 1
    #classifier_host = curr_deployment['classifier-app'][0]['name']
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
    # Get app metric (1)
    #classifier_fps = mlsClient.get_metric_value_with_label(metric_name="classifier_fps")
    # Get app metric (2)
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
    
    
    # Get cpu/gpu util consumption mode for vader/jetson (low/high)
    # vader_cpu_util = mlsClient.get_metric_value_with_label(metric_name="vader_cpu_util")
    # if vader_cpu_util is None:
    #     logger.info("vader_cpu_util is None")
    # vader_gpu_util = mlsClient.get_metric_value_with_label(metric_name="vader_gpu_util")
    # if vader_gpu_util is None:
    #     logger.info("vader_gpu_util is None")
    # jetson_cpu_util = mlsClient.get_metric_value_with_label(metric_name="jetson_cpu_util")
    # if jetson_cpu_util is None:
    #     logger.info("jetson_cpu_util is None")
    # jetson_gpu_util = mlsClient.get_metric_value_with_label(metric_name="jetson_gpu_util")
    # if jetson_gpu_util is None:
    #     logger.info("jetson_gpu_util is None")
    
    
    # logger.info('low_latency_threshold %s', low_latency_threshold)
    # logger.info('high_latency_threshold %s', high_latency_threshold)
    # logger.info('qos_target %s', qos_target)
    # if host = jetson and latency > low_latency_threshold --> move to Vader
    # elif host = jetson and latency < low_latency_threshold --> keep comp on jetson
    # elif host = vader and latency > low_latency_threshold and latency < high_latency_threshold
    #       If QoS > mean_threshold --> relocate to jetson (need to specify that threshold)
    #       Else if QoS < mean_threshold or QoS < target_fps < , keep component on vader
    # elif host = vader and latency > high_latency_threshold, keep component on vader
    # TODO: DOUBLE CHECK THOSE
    curr_timestamp = time.time()
    
    if prev_timestamp is not None:
        diff = curr_timestamp - prev_timestamp
        logger.info('Timestamp diff %s', diff)
    else:
        # Make diff = 0 to identify the first time for relocation
        diff = -1
    if classifier_host == 'csl-jetson1' and average_latency > jetson_bottom_latency_threshold: #and (diff > 20 or diff == -1):
        logger.info('Host is jetson and latency > low_latency_threshold. cmd=Move to vader.')
        current_command = "move_classifier_to_vader"
        latency_window = deque([0] * latency_window.maxlen, maxlen=latency_window.maxlen)
        logger.info("Deque reset to zeros: %s", latency_window)
        prev_timestamp = curr_timestamp
        return True, context
    elif classifier_host == 'csl-jetson1' and average_latency < jetson_bottom_latency_threshold:
        return False, context
    #elif classifier_host == 'csl-vader' and latency > vader_bottom_latency_threshold and latency < vader_top_latency_threshold and vader_power == 'L':
    elif classifier_host == 'csl-vader' and average_latency < vader_top_latency_threshold and vader_power_value != None and vader_power_value == 0: #and (diff > 13 or diff == -1): #and latency < vader_top_latency_threshold and vader_power == 'L':
        # if latency > ((high_latency_threshold + low_latency_threshold)/2):
        #     return False, context
        # else:
        logger.info('Host is vader and high_latency_threshold > latency > low_latency_threshold. cmd=Move to jetson.')
        # In this case it is safe to move to jetson since Jetson(H) and Vader(L)they have similar performance
        current_command = "move_classifier_to_jetson"
        latency_window = deque([0] * latency_window.maxlen, maxlen=latency_window.maxlen)
        logger.info("Deque reset to zeros: %s", latency_window)
        prev_timestamp = curr_timestamp
        return True, context
    elif classifier_host == 'csl-vader' and average_latency > vader_top_latency_threshold:
        return False, context
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

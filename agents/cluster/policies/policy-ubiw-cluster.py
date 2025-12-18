# """Plugin module for custom policies - notify function."""
from __future__ import print_function
import pprint
import copy
import logging
import os
import time
import inspect
import random

from mlstelemetry import MLSTelemetry

from mlsysops.logger_util import logger

mlsClient = MLSTelemetry("fluidity_mechanism", "ubiwhere_policy")

from sismic.io import import_from_yaml
from sismic.model import Statechart
from sismic.interpreter import Interpreter

analyze_counter = 0

class ClusterAgentFSM:
    internalState = None
    stateInterperter = None

    def __init__(self, name, command_handler):
        self.name = name

        self.internalState = import_from_yaml(filepath="policies/Ubiwhere_FSM.yaml")
        assert isinstance(self.internalState, Statechart)

        # Create an interpreter for this statechart
        self.stateInterperter = Interpreter(self.internalState, initial_context={'send_command':command_handler})
        initStep = self.stateInterperter.execute_once()

    def __str__(self):
        return f"{self.name}: {self.internalState}"

    def print_status(self, step):
        # possible values: ['event', 'transitions', 'entered_states', 'exited_states', 'sent_events']
        return_str = ""
        previous_s = []
        actual_s = []
        for attribute in ['event', 'transitions', 'entered_states', 'exited_states', 'sent_events']:
            print('{} current state: {}'.format(attribute, getattr(step, attribute)))
            return_str = return_str + '{} current state: {}'.format(attribute, getattr(step, attribute))

        actual_s = getattr(step, 'entered_states')
        previous_s = getattr(step, 'exited_states')
        if previous_s == []:
            previous_s = None
        else:
            previous_s = previous_s[0]
        if actual_s == []:
            actual_s = None
        else:
            actual_s = actual_s[0]
        return return_str,previous_s,actual_s

    def get_status(self):
        if len(self.stateInterperter.configuration) > 1:
            print(self.stateInterperter.configuration)
            return self.stateInterperter.configuration[1]
        else:
            return "removed"

    def set_event(self, event):
        step = self.stateInterperter.queue(event).execute_once()
        return self.print_status(step)


logger = logging.getLogger(__name__)
current_command = ''
# TODO: To be removed -- START
test_counter = 0
# NOTE: To be removed -- END
noise_threshold = 10
camera_threshold = 11

def update_comand(command):
    global current_command

    logger.error('in update_comand, prev_cmd %s', current_command)
    logger.error('in update_comand, curr_cmd %s', command)

    current_command = command

fsm = ClusterAgentFSM('ubi-app', update_comand)


def generate_event(status,snapshot):
    event = ""
    if status == "S1":  # Both NAVL
        if snapshot['L'] == "AVL": #S2
            return "lamppost_appears"
        else:
            return "No event"
    elif status == "S2":  # T NAVL D AVL
        if snapshot['L'] == "NAVL": #S1
            return "lamppost_disappears"
        # elif snapshot['I'] == "LP": #S3
        #     return "image_LP"
        elif snapshot['N'] == "LP": #S5
            return "noise_LP"
        else:
            return "No event"
    # elif status == "S3":  # T  OK D AVL
    #     if snapshot['L'] == "NAVL":  # S1
    #         return "lamppost_disappears"
    #     elif snapshot['I'] == "HP":  # S2
    #         return "image_HP"
    #     elif snapshot['N'] == "LP":  # S5
    #         return "noise_LP"
    #     else:
    #         return "No event"
    # elif status == "S4":  # T  OK D NAVL
    #     if snapshot['L'] == "NAVL":  # S1
    #         return "lamppost_disappears"
    #     elif snapshot['N'] == "HP":  # S2
    #         return "image_HP"
    #     elif snapshot['I'] == "LP":  # S5
    #         return "image_LP"
    #     else:
    #         return "No event"
    elif status == "S5":  # T NOK D NAVL
        if snapshot['L'] == "NAVL":  # S1
            return "lamppost_disappears"
        elif snapshot['N'] == "HP":  # S2
            return "noise_inference_from_LP_to_HP"
        else:
            return "No event"




def parse_analyze_interval(interval: str) -> int:
    """
    Parses an analyze interval string in the format 'Xs|Xm|Xh|Xd' and converts it to seconds.

    Args:
        interval (str): The analyze interval as a string (e.g., "5m", "2h", "1d").

    Returns:
        int: The interval in seconds.

    Raises:
        ValueError: If the format of the interval string is invalid.
    """
    # Match the string using a regex: an integer followed by one of s/m/h/d
    match = re.fullmatch(r"(\d+)([smhd])", interval)
    if not match:
        raise ValueError(f"Invalid analyze interval format: '{interval}'")

    # Extract the numeric value and the time unit
    value, unit = int(match.group(1)), match.group(2)

    # Convert to seconds based on the unit
    if unit == "s":  # Seconds
        return value
    elif unit == "m":  # Minutes
        return value * 60
    elif unit == "h":  # Hours
        return value * 60 * 60
    elif unit == "d":  # Days
        return value * 24 * 60 * 60
    else:
        raise ValueError(f"Unsupported time unit '{unit}' in interval: '{interval}'")


def initialize():
    print(f"Initializing policy {inspect.stack()[1].filename}")

    initialContext = {
        "telemetry": {
            "metrics": ["node_app_prediction"],
            "system_scrape_interval": "1s"
        },
        "mechanisms": [
            "fluidity"
        ],
        "packages": ["sismic"],
        "configuration": {
            "analyze_interval": "15s"
        },
        "noise_app_deployed": False,
        "noise_app_init_deployment": True,
        "lamppost_ready": False,
        "lamppost_hostname": None,
        "camera_app_deployed": False,
        "latest_timestamp": None,
        "core": True,
        "scope": "application",
        "current_placement": None,
        "initial_deployment_finished": False,
        "moving_interval": "30s",
        "dynamic_placement_comp": None
    }

    return initialContext

def get_first_node(cluster_description):
    return cluster_description['nodes'][0]



async def get_metric(metric_name, telemetry):
    # Get latest values from telemetry data
    component_measured_metric = None
    try:
        latest_telemetry_df = await telemetry['query'](latest=True)
        #latest_telemetry_df = telemetry['query'](latest=True)
        component_measured_metric = latest_telemetry_df[metric_name].values[0]
        logger.debug(f"metric {metric_name} measurement {component_measured_metric} ")
    except Exception as e:
        logger.error(f"Failed to get metric {metric_name}")

    return component_measured_metric



""" Plugin function to implement the initial deployment logic.
"""
async def initial_plan(context, app_desc, system_description, mechanisms, telemetry):
    # NOTE: The parsing of app_desc which the fluidity handles, should be moved here.
    logger.error('initial deployment phase')
    global current_command
    global fsm
    global analyze_counter
    analyze_counter = 0

    components_state = mechanisms['fluidity']['state']['applications'][context['name']]['components']

    context['component_names'] = []
    for component in app_desc['spec']['components']:
        comp_name = component['metadata']['name']
        context['component_names'].append(comp_name)
        if 'noise' in comp_name and comp_name in components_state:
            context["noise_app_deployed"] = components_state[comp_name]['node_placed']
        elif 'proxy-cv' in comp_name and comp_name in components_state:
            context["camera_app_deployed"] = components_state[comp_name]['node_placed']
            context["lamppost_hostname"] = component['node_placement']['node']

    #logger.error('initial deployment phase ', app_desc)
    logger.error(f"component_names {context['component_names']}")

    context['FSM'] = fsm
    context['name'] = app_desc['name']
    context['spec'] = app_desc['spec']

    logger.error('app_desc[spec] %s', app_desc['spec'])
    snapshot = {
        'I': 'None', # Image-based detection component
        'N': 'None', # Noise-based detection component
        'L': 'None'  # Lamppost node.
    }
    plan = {}

    for node_name in mechanisms['fluidity']['state']['nodes']:
        #logger.error(f"mechanisms for node {node_name}: {mechanisms['fluidity']['state']['nodes'][node_name]}")

        node = mechanisms['fluidity']['state']['nodes'][node_name]
        if 'spec' not in node:
            continue
        if node_name == context["lamppost_hostname"]:
            context["lamppost_ready"] = node['ready']
        if 'labels' not in node['spec'] or 'node-type:lamppost' not in node['spec']['labels']:
            continue
        if 'node-type:lamppost' in node['spec']['labels']:
            context["lamppost_ready"] = node['ready']

    logger.error(f"context['lamppost_ready'] {context['lamppost_ready']}")

    if context["lamppost_hostname"] == None:
        logger.error('Did not find any candidate nodes. Going to return.')
        return plan
    if not context["lamppost_ready"] :
        snapshot['L'] = 'NAVL'
        logger.error('Lamppost is not ready. Going to return false.')
        return plan
    else:
        logger.error('Lamppost is ready. ')
        snapshot['L'] = 'AVL'

    try:
        status = context["FSM"].get_status()
        logger.error(f"Got status {status}")
        event = generate_event(status, snapshot)
        logger.error(f"event {event}")
        context['prev_snapshot'] = snapshot
        logger.error(f"prev_snapshot {context['prev_snapshot']}")
        # if event != "" and event != "No event":
        #     mlsClient.pushLogInfo("TR Event: " + event)
        # logger.error(f"TR Event: {event}")
        context['transition_result'], context['previous_state'], context['actual_state'] = context["FSM"].set_event(event)
        if context['previous_state'] == None:
            logger.error('previous_state is None')
        # if context['actual_state'] != None and context['previous_state'] != None:
        #     mlsClient.pushLogInfo("TR: " + context['previous_state'] + " -> " + context['actual_state'])

        status = context["FSM"].get_status()
        logger.error(f"Got new status {status}")
        # if event != "" and event != None:
        #     mlsClient.pushLogInfo("Caught event: " + event)
        # mlsClient.pushLogInfo("CS: " + status)
    except Exception as e:
        logger.error(f"Caught exception {e}")


    cmd = current_command
    logger.error(f"cmd is {cmd}")
    if cmd == "NONE":
        logger.error('Empty cmd.')
    #elif cmd == 'start_image_start_noise':
    elif cmd == 'start_image' and not context["camera_app_deployed"]:
        plan = {}
        for component in context['component_names']:
            plan[component] = [{'action': 'deploy', 'host': context["lamppost_hostname"]}]
            #logger.error(f"Adding deploy for {plan[component]}")
        context['initial_deployment_finished'] = True
    logger.error('Initial plan returning plan %s' % plan)
    logger.error(status)
    return plan


async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    global current_command
    global noise_threshold
    global camera_threshold

    application = application_description[0]
    context['name'] = application['name']
    components_state = mechanisms['fluidity']['state']['applications'][context['name']]['components']

    if 'initial_deployment_finished' in context and context['initial_deployment_finished'] == False:
        return True, context

    for component in application['spec']['components']:
        comp_name = component['metadata']['name']
        if 'proxy-cv' in comp_name and comp_name in components_state:
            context["camera_app_deployed"] = components_state[comp_name]['node_placed']


    for node_name in mechanisms['fluidity']['state']['nodes']:
        #logger.error(f"mechanisms for node {node_name}: {mechanisms['fluidity']['state']['nodes'][node_name]}")

        node = mechanisms['fluidity']['state']['nodes'][node_name]
        if 'spec' not in node:
            continue
        if node_name == context["lamppost_hostname"]:
            context["lamppost_ready"] = node['ready']
        if 'labels' not in node['spec'] or 'node-type:lamppost' not in node['spec']['labels']:
            continue
        if 'node-type:lamppost' in node['spec']['labels']:
            context["lamppost_ready"] = node['ready']

    snapshot = {
        'I': 'None',
        'N': 'None',
        'L': 'None'
    }
    # TODO: To be removed -- START
    # time.sleep(5)
    # global analyze_counter
    # analyze_counter +=1
    # logger.error(f"analyze_counter {analyze_counter}")

    # if analyze_counter % 6 == 0:
    #     logger.error(f"returning true")
    #     return True, context

    # return False, context

    # NOTE: To be removed -- END
    logger.error('Prev snapshot was %s', context['prev_snapshot'])
    #if curr_deployment['proxy-cv'][0]['status'] == 'ACTIVE':
    if context["camera_app_deployed"]:
        snapshot['I'] = 'RUN'

    #if curr_deployment['noise-detection-app'][0]['status'] == 'ACTIVE':
    snapshot['N'] = 'RUN'

    status = context["FSM"].get_status()

    #camera_host = curr_deployment['proxy-cv'][0]['name']
    camera_host = context["lamppost_hostname"]
    #noise_host = curr_deployment['noise-detection-app'][0]['name']
    noise_host = camera_host
    #collector_host = curr_deployment['collector-app'][0]['name']
    #logger.error('camera_host: %s, noise_host: %s, collector_host: %s', camera_host, noise_host, collector_host)
    logger.error(f"camera_host: {camera_host}, noise_host: {noise_host}, lamposthostname {context['lamppost_hostname']}")

    # If the noise app is running, retrieve the app-level metric.
    # if curr_deployment['noise-detection-app'][0]['status'] == 'ACTIVE' and get_node_availability(noise_host,
    #                                                                                    nodes['k8snodes']):
    #if get_node_availability(noise_host, nodes['k8snodes']):
    if context["lamppost_ready"]:
        #noise_prediction = mlsClient.get_metric_value_with_label(metric_name="node_app_prediction")
        #noise_prediction = await get_metric("node_app_prediction", telemetry)

        metric_object = mlsClient.get_metric_value_with_label(metric_name="node_app_prediction",label_name="node_name", label_value=context["lamppost_hostname"])
        if metric_object:
            noise_prediction = metric_object[0].get("value", 0)
            logger.error(f"App {application['name']} received metric {noise_prediction} from host {context['lamppost_hostname']}")
        else:
            noise_prediction = None

        if noise_prediction == None or noise_prediction == 0: #or noise_prediction['value'] == 'NA':
            logger.error('Did not receive any metrics from noise-app yet.')
            snapshot['N'] = 'RUN'
        else:
            logger.error('App noise detection prediction is %s', noise_prediction)
            #if noise_prediction['value'] >= noise_threshold:

            noise_prediction = float(noise_prediction) + random.uniform(-1, 1)
            logger.error('MODIFIED App noise detection prediction is %s', noise_prediction)
            if noise_prediction >= noise_threshold:
                logger.error(f"Detected HIGH probability {noise_prediction}")
                snapshot['N'] = 'HP'
            else:
                logger.error(f"Detected LOW probability {noise_prediction}")
                snapshot['N'] = 'LP'

    snapshot['I'] = 'RUN'
    # If the camera app is running, retrieve the app-level metric.
    # if curr_deployment['proxy-cv'][0]['status'] == 'ACTIVE' and get_node_availability(camera_host,
    #                                                                                     nodes['k8snodes']):
    #     camera_prediction = mlsClient.get_metric_value_with_label(metric_name="camera_app_prediction")
    #     if camera_prediction == None or camera_prediction['value'] == 'NA':
    #         logger.error('Did not receive any metrics from proxy-cv yet.')
    #         snapshot['I'] = 'RUN'
    #     else:
    #         logger.error('App camera detection prediction is %s', camera_prediction['value'])
    #         if camera_prediction['value'] >= camera_threshold:
    #             snapshot['I'] = 'HP'
    #         else:
    #             snapshot['I'] = 'LP'

    #if get_node_availability(noise_host, nodes['k8snodes']) == False:
    if not context["lamppost_ready"]:
        snapshot['L'] = 'NAVL'
    else:
        snapshot['L'] = 'AVL'

    # logger.error('Previous snapshot %s', context['prev_snapshot'])
    # logger.error('Current snapshot %s', snapshot)

    logger.error('Current status %s', status)
    event = generate_event(status, snapshot)
    # mlsClient.pushLogInfo("Previous noise state: " + context['prev_snapshot']['N'])
    # mlsClient.pushLogInfo("Previous camera state: " + context['prev_snapshot']['I'])
    # mlsClient.pushLogInfo("Previous lamppost state: " + context['prev_snapshot']['L'])
    # mlsClient.pushLogInfo("Current noise state: " + snapshot['N'])
    # mlsClient.pushLogInfo("Current camera state: " + snapshot['I'])
    # mlsClient.pushLogInfo("Current lamppost state: " + snapshot['L'])
    # if event != "" and event != "No event":
    #     mlsClient.pushLogInfo("TR Event: " + event)

    context['prev_snapshot'] = snapshot
    logger.error(event)

    context['transition_result'], context['previous_state'], context['actual_state'] = context["FSM"].set_event(event)
    if context['previous_state'] == None:
        logger.error('previous_state is None')
    # if context['actual_state'] != None and context['previous_state'] != None:
    #     mlsClient.pushLogInfo("TR: " + context['previous_state'] + " -> " + context['actual_state'])

    status = context["FSM"].get_status()
    # if event != "" and event != None:
    #     mlsClient.pushLogInfo("Caught event: " + event)
    # mlsClient.pushLogInfo("CS: " + status)

    # logger.error(status)
    # time.sleep(10)
    if context['previous_state'] != None and context['actual_state'] != None:
        return True, context
    else:
        return False, context


async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    # Possible commands to Fluidity
    # 1. 'start_image_start_noise'
    # 2. 'start_image'
    # 3. 'stop_image_stop_noise'
    # 4. 'stop_image'
    # 5. 'stop_noise'

    global current_command
    # TODO: To be removed -- START
    global test_counter
    # NOTE: To be removed -- END
    # logger.error('Curr deployment: %s', curr_deployment)
    # camera_host = curr_deployment['proxy-cv'][0]['name']
    # noise_host = curr_deployment['noise-detection-app'][0]['name']
    # collector_host = curr_deployment['collector-app'][0]['name']
    # logger.error('camera_host: %s, noise_host: %s, collector_host: %s', camera_host, noise_host, collector_host)

    application = application_description[0]
    components_state = mechanisms['fluidity']['state']['applications'][context['name']]['components']
    logger.error(f"components_state {components_state}")

    # TODO: Check if this should be moved to else below
    #status = context["FSM"].get_status()
    plan_result = {
        'deployment_plan': {},
    }

    if 'initial_deployment_finished' in context and context['initial_deployment_finished'] == False:
        # NOTE: Check if context is updated properly after the invocation
        initial_plan_result = await initial_plan(context, application, system_description, mechanisms, telemetry)
        if initial_plan_result:
            plan_result['deployment_plan'] = initial_plan_result
            plan_result['deployment_plan']['initial_plan'] = True
        else:
            logger.error(f"INITIAL PLAN FAILED")
            logger.error(f"plan_result {plan_result}")
            return plan_result, context
    else:
        plan_result['deployment_plan']['initial_plan'] = False

        cmd = current_command

        # TODO: To be removed -- START
        #time.sleep(10)
        # temp_result = test_counter % 6
        # # send_command("start_image_start_noise")
        # # send_command("stop_image_stop_noise")
        # # send_command("stop_image")
        # # send_command("stop_noise")
        # # send_command("start_image")
        # if temp_result == 0:
        #     cmd = "stop_image"
        # elif temp_result == 1:
        #     cmd = "start_image"
        # elif temp_result == 2:
        #     #cmd = "stop_noise"
        #     cmd = "NONE"
        # elif temp_result == 3:
        #     cmd = "NONE"
        #     #cmd = "start_noise"
        # elif temp_result == 4:
        #     cmd = "stop_image"
        #     #cmd = "stop_image_stop_noise"
        # elif temp_result == 5:
        #     cmd = "start_image"
        #     #cmd = "start_image_start_noise"

        # test_counter +=1
        # NOTE: To be removed -- END
        # Creation of the plan_result as actions to be
        # provided to Fluidity's internal mechanism.
        logger.error('cmd is %s', cmd)
        if cmd == "NONE":
            logger.error('Empty cmd.')
        # mlsClient.pushLogInfo("Current app deployment: "+curr_deployment)
        #mlsClient.pushLogInfo("Fluidity will execute command: " + cmd)

        for comp in application['spec']['components']:
            comp_name = comp['metadata']['name']
            logger.error(comp_name)
            # if comp_name == 'noise-detection-app':
            #     if 'start_noise' in cmd and (comp_name not in components_state or not components_state[comp_name]['node_placed']):
            #         plan_result['curr_deployment'][comp_name] = {
            #             'action': 'deploy',
            #             'host': context["lamppost_hostname"]
            #         }
            #     elif 'stop_noise' in cmd and (comp_name in components_state and components_state[comp_name]['node_placed']):
            #         plan_result['curr_deployment'][comp_name] = {
            #             'action': 'remove',
            #             'host': context["lamppost_hostname"]
            #         }
            if 'proxy-cv' in comp_name:
                if 'start_image' in cmd and (comp_name not in components_state or not components_state[comp_name]['node_placed']):
                    plan_result['deployment_plan'][comp_name] = [{
                        'action': 'deploy',
                        'host': context["lamppost_hostname"]
                    }]
                if 'stop_image' in cmd and (comp_name in components_state and components_state[comp_name]['node_placed']):
                    plan_result['deployment_plan'][comp_name] = [{
                        'action': 'remove',
                        'host': context["lamppost_hostname"]
                    }]
        logger.error('Actions to be returned to Fluidity %s' % plan_result)

    logger.error('plan: New plan %s', plan_result)
    fluidity_dict = {
        'deployment_plan': plan_result['deployment_plan'],
        'name': context['name']
    }

    new_plan = {
        "fluidity": fluidity_dict
    }


    return new_plan, context

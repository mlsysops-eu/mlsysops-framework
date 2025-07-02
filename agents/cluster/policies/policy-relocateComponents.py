"""Plugin module for custom policies - notify function."""
from __future__ import print_function

import inspect
import re
import time
import logging

from mlsysops.logger_util import logger


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
            "metrics": ["node_load1"],
            "system_scrape_interval": "5s"
        },
        "mechanisms": [
            "fluidity_proxy"
        ],
        "packages": [],
        "configuration": {
            "analyze_interval": "10s"
        },
        "latest_timestamp": None,
        "core": False,
        "scope": "application",
        "current_placement": None,
        "initial_deployment_finished": False,
        "moving_interval": "30s",
        "dynamic_placement_comp": None
    }

    return initialContext

def get_first_node(cluster_description):
    return cluster_description['nodes'][0]


""" Plugin function to implement the initial deployment logic.
"""
def initial_plan(context, app_desc, system_description):
    logger.info('initial deployment phase ', app_desc)

    context['name'] = app_desc['name']
    context['spec'] = app_desc['spec']
    context['initial_deployment_finished'] = True
    context['component_names'] = []
    plan = {}

    context['main_node'] = system_description['MLSysOpsCluster']['nodes'][0]
    context['alternative_node'] = system_description['MLSysOpsCluster']['nodes'][1]
    context["current_placement"] = get_first_node(system_description['MLSysOpsCluster'])

    for component in app_desc['spec']['components']:
        comp_name = component['metadata']['name']
        logger.info('component %s', comp_name)
        context['component_names'].append(comp_name)
        node_placement = component.get("node_placement")
        if node_placement:
            node_name = node_placement.get("node", None)
            if node_name:
                logger.info('Found node name. Will continue')
                continue
        context['dynamic_placement_comp'] = comp_name
        plan[comp_name] = [{'action': 'deploy', 'host': context["current_placement"]}]
    logger.info('Initial plan %s', plan)
    return plan, context

async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    logger.info(f"\nTelemetry {telemetry}")
    
    current_timestamp = time.time()

    # The first time called
    if context['latest_timestamp'] is None:
        context['latest_timestamp'] = current_timestamp
        return True, context

    # All the next ones, get it
    analyze_interval = parse_analyze_interval(context['moving_interval'])
    if current_timestamp - context['latest_timestamp'] > analyze_interval:
        context['latest_timestamp'] = current_timestamp
        return True, context

    return False, context



async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    #logger.info(f"Called relocation plan  ----- {mechanisms}")
    
    context['initial_plan'] = False
    
    plan_result = {}
    plan_result['deployment_plan'] = {}
    application = application_description[0]
    
    if 'initial_deployment_finished' in context and context['initial_deployment_finished'] == False:
        initial_plan_result, new_context = initial_plan(context, application, system_description)
        if initial_plan_result:
            plan_result['deployment_plan'] = initial_plan_result
            plan_result['deployment_plan']['initial_plan'] = True

            comp_name = new_context['dynamic_placement_comp']
    else:
        comp_name = context['dynamic_placement_comp']
        plan_result['deployment_plan']['initial_plan'] = False
        plan_result['deployment_plan'][comp_name] = []
        curr_plan = {}

        if context['main_node'] == context["current_placement"]:
            curr_plan = {
                "action": "move",
                "target_host": context['alternative_node'],
                "src_host": context['main_node'],
            }
            context["current_placement"] = context['alternative_node']
        elif context['alternative_node'] == context["current_placement"]:
            curr_plan = {
                "action": "move",
                "target_host": context['main_node'],
                "src_host": context['alternative_node'],
            }
            context["current_placement"] = context['main_node']
        
        plan_result['deployment_plan'][comp_name].append(curr_plan)
    

    if plan_result:
        plan_result['name'] = context['name']

    new_plan = {
        "fluidity": plan_result,
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context

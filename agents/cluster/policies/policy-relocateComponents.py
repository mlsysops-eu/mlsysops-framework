"""Plugin module for custom policies - notify function."""
from __future__ import print_function

import inspect
import re
import time
import logging

logger = logging.getLogger(__name__)

node_one = "csl-rpi5-1"
node_two = "csl-vader"

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
            "system_scrape_interval": "1s"
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
        "current_placement": "mls-ubiw-2",
        "moving_interval": "30s"
    }

    return initialContext


def analyze(context, application_description, system_description, current_plan, telemetry, ml_connector):
    # a simple policy that periodically changes the frequency of the node
    # Analyze
    print("Called analyze of relocation ", context)
    logger.info(f"\nTelemetry {telemetry}")
    #await asyncio.sleep(10)
    #time.sleep(30)
    current_timestamp = time.time()

    # The first time called
    if context['latest_timestamp'] is None:
        context['latest_timestamp'] = current_timestamp
        return False, context

    # All the next ones, get it
    analyze_interval = parse_analyze_interval(context['moving_interval'])
    print(f"{current_timestamp} - {context['latest_timestamp']}  = {current_timestamp - context['latest_timestamp']} with interval {analyze_interval}")
    if current_timestamp - context['latest_timestamp'] > analyze_interval:
        context['latest_timestamp'] = current_timestamp
        return True, context

    return False, context



def plan(context, application_description, system_description, current_plan, telemetry, ml_connector, available_assets):
    print("Called relocation plan  ----- ", current_plan)
    
    context['initial_plan'] = False
    main_node = node_one
    alternative_node = node_two

    plan_result = {}
    plan_result['deployment_plan'] = {}
    plan_result['deployment_plan']['server-app'] = []
    curr_plan = {}
    if main_node == context["current_placement"]:
        curr_plan = {
            "action": "move",
            "target_host": alternative_node,
            "src_host": main_node,
        }
        context["current_placement"] = alternative_node

    elif alternative_node == context["current_placement"]:
        curr_plan = {
            "action": "move",
            "target_host": main_node,
            "src_host": alternative_node,
        }
        context["current_placement"] = main_node

    plan_result['deployment_plan']['server-app'].append(curr_plan)
    if not context['initial_plan']:
        context['name'] = application_description[0]['name']
        context['initial_plan'] = True
        
    # This policy produces a plan for reconfiguration and not for the initial
    # deployment
    plan_result['deployment_plan']['initial_plan'] = False


    if plan_result:
        plan_result['name'] = context['name']

    new_plan = {
        "fluidity": plan_result,
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context

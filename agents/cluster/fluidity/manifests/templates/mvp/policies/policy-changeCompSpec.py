"""Plugin module for custom policies - notify function."""
from __future__ import print_function
import copy
import logging
import inspect
from itertools import cycle
import random
import time
import re
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


spec_changes = cycle([
    {'image': cycle(['harbor.nbfc.io/mlsysops/test-app:sha-90e0077', 'harbor.nbfc.io/mlsysops/test-app:latest'])},
    {'platform_requirements': {
            'cpu': { 
                'requests': '', # in m
                'limits': '' # in m
            },
            'memory': {
                'requests':  '', # in Mi
                'limits':  '' # in Mi
            }
        }
    }
])


def initialize():
    logger.info(f"Initializing policy {inspect.stack()[1].filename}")

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
            "analyze_interval": "30s"
        },
        "latest_timestamp": None,
        "core": False,
        "scope": "application",
        "curr_comp_idx": 0,
        "current_placement": None,
        "initial_deployment_finished": False,
        "moving_interval": "30s",
        "dynamic_placement_comp": None
    }

    return initialContext


def get_curr_container_img(comp_name, context):
    for comp in context['spec']['components']:
        if comp_name != comp['metadata']['name']:
            continue

        container = comp.get("containers")[0]['image']
        
        return container


async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    current_timestamp = time.time()

    # The first time called
    if context['latest_timestamp'] is None:
        context['latest_timestamp'] = current_timestamp
        return True, context

    # All the next ones, get it
    analyze_interval = parse_analyze_interval(context['moving_interval'])
    logger.info(f"{current_timestamp} - {context['latest_timestamp']}  = {current_timestamp - context['latest_timestamp']} with interval {analyze_interval}")
    
    if current_timestamp - context['latest_timestamp'] > analyze_interval:
        context['latest_timestamp'] = current_timestamp
        return True, context
    
    return True, context


async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    plan_result = {}
    plan_result['deployment_plan'] = {}
    application = application_description[0]
    description_changed = False
    change_idx = cycle([0, 1, 2])
    curr_change = next(spec_changes)
    
    #logger.info(f'Curr change is {curr_change}')
    component = application['spec']['components'][0]
    comp_name = component['metadata']['name']
    logger.info(f'component spec {component}')
    if 'node_placement' in component and 'node' in component['node_placement']:
        node = component['node_placement']['node']
        logger.info(f'Found static placement on {node} for comp {comp_name}')
    else: 
        node = system_description['MLSysOpsCluster']['nodes'][0]
        logger.info(f'Randomly select host {node} for {comp_name}')
    
    plan_result['deployment_plan'][comp_name] = []
    
    for key in curr_change:
        logger.info(f"key is {key}")
        # logger.info(f"curr_change[key] is {curr_change[key]}")
        # logger.info(f"next(curr_change[key]) is {next(curr_change[key])}")
        if key == 'runtime_class_name': 
            component[key] = next(curr_change[key])
        else:
            for container in component['containers']:

                if key == 'image':
                    container[key] = next(curr_change[key])
                    continue

                request_cpu = str(random.randint(0, 300))
                limit_cpu = str(random.randint(301, 400))
                cpu_suffix = 'm'

                request_mem = str(random.randint(0, 300))
                limit_mem = str(random.randint(301, 400))
                mem_suffix = 'Mi'
                logger.info(f'request_cpu+cpu_suffix {request_cpu+cpu_suffix}')

                if key not in container or 'cpu' not in container[key] or 'memory' not in container[key]:
                    container[key] = {
                        'cpu': {
                            'requests': '',
                            'limits': ''
                        },
                        'memory': {
                            'requests': '',
                            'limits': ''
                        }
                    }

                container[key]['cpu']['requests'] = request_cpu+cpu_suffix
                container[key]['cpu']['limits'] = limit_cpu+cpu_suffix

                container[key]['memory']['requests'] = request_mem+mem_suffix
                container[key]['memory']['limits'] = limit_mem+mem_suffix

        plan_result['deployment_plan'][comp_name].append({'action': 'change_spec', 'new_spec': component, 'host': node})
        logger.info(f"Applying change type {key} to comp {comp_name}, new spec is {component}")
   

    if plan_result:
        plan_result['name'] = application['name']
        # This policy will only take effect after initial deployment is done.
        plan_result['deployment_plan']['initial_plan'] = False

    new_plan = {
        "fluidity": plan_result
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context

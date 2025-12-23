"""Plugin module for custom policies - notify function."""
from __future__ import print_function

import inspect
import re
import time
import logging
import random

from mlsysops.logger_util import logger
from mlsysops.utilities import evaluate_condition, parse_analyze_interval

def initialize():
    print(f"Initializing policy {inspect.stack()[1].filename}")

    initialContext = {
        "telemetry": {
            "metrics": [],
            "system_scrape_interval": "1s"
        },
        "mechanisms": ["fita"],
        "packages": [],
        "configuration": {
            "analyze_interval": "5s"
        },
        "latest_timestamp": None,
        "core": False,
        "scope": "application",
        "moving_interval": "30s"
    }

    return initialContext

async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    current_timestamp = time.time()

    # The first time called
    if context['latest_timestamp'] is None:
        context['latest_timestamp'] = current_timestamp
        return True, context

    # All the next ones, get it
    analyze_interval = parse_analyze_interval(context['moving_interval'])
    logger.info(
        f"{current_timestamp} - {context['latest_timestamp']}  = {current_timestamp - context['latest_timestamp']} with interval {analyze_interval}")

    if current_timestamp - context['latest_timestamp'] > analyze_interval:
        context['latest_timestamp'] = current_timestamp
        return True, context

    return False, context


async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):

    application = application_description[0]

    # check if in the state the client app has been placed
    # use fluidity state for that
    components_state = mechanisms['fluidity']['state']['applications'][application_description[0]['name']]['components']
    logger.info('Clalled plan')

    context['name'] = application['name']
    context['spec'] = application['spec']

    plan_result = {}
    plan_result['name'] = context['name']
    plan_result['deployment_plan'] = {}

    for component in application['spec']['components']:
        logger.debug(f'11 component: {component}')
        comp_name = component['metadata']['name']
        node_placement = component.get("node_placement")

        current_node_placed = components_state[comp_name]['node_placed']
        if current_node_placed is not None:
            # component is placed, move it to another
            available_nodes = [node for node in system_description['MLSysOpsCluster']['nodes'] if node != current_node_placed and "b1" in node]

            node_to_place = random.choice(available_nodes)

            new_component_plan = {
                "action": "move",
                "target_host": node_to_place,
                "src_host": current_node_placed,
            }
            if comp_name not in plan_result['deployment_plan']:
                plan_result['deployment_plan'][comp_name] = []

            plan_result['deployment_plan'][comp_name].append(new_component_plan)

    if len(plan_result['deployment_plan'].keys()) == 0:
        return {}, context # no plan produced

    plan_result['deployment_plan']['initial_plan'] = False

    new_plan = {
        "fluidity": plan_result,
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context

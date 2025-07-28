"""Plugin module for custom policies - notify function."""
from __future__ import print_function

import inspect
import re
import time
import logging
import random

from mlsysops.logger_util import logger
from mlsysops.utilities import evaluate_condition

def initialize():
    logger.info(f"Initializing policy {inspect.stack()[1].filename}")

    initialContext = {
        "telemetry": {
            "metrics": ["node_load1"],
            "system_scrape_interval": "5s"
        },
        "mechanisms": ["fluidity"],
        "packages": [],
        "configuration": {
            "analyze_interval": "5s"
        },
        "scope": "application",
    }

    return initialContext

async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):

    # policy handles single policy, always an array with a single application
    application_spec = application_description[0]['spec']
    application_components = application_spec['components']

    for application_component in application_components:
        component_metrics = application_component['qos_metrics']
        for component_metric in component_metrics:
            metric_name = component_metric['application_metric_id']
            # Get latest values from telemetry data
            try:
                latest_telemetry_df = await telemetry['query'](latest=True)
            except Exception as e:
                continue
            component_metric_target = component_metric['target']
            component_measured_metric = latest_telemetry_df[metric_name].values[0]
            logger.debug(
                f"metric {metric_name} Target {component_metric_target} measurement {component_measured_metric} ")

            if component_measured_metric is None:
                continue

            if evaluate_condition(component_metric_target,component_measured_metric, component_metric['relation']):
                # even one telemetry metric is not fulfilled, return true
                return True, context

    return False, context


async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):

    application = application_description[0]
    
    # check if in the state the client app has been placed
    # use fluidity state for that
    components_state = mechanisms['fluidity']['state']['applications'][application_description[0]['name']]['components']

    context['name'] = application['name']
    context['spec'] = application['spec']

    plan_result = {}
    plan_result['name'] = context['name']
    plan_result['deployment_plan'] = {}

    for component in application['spec']['components']:
        comp_name = component['metadata']['name']
        node_placement = component.get("node_placement")

        if node_placement:
            node_name = node_placement.get("node", None)
            if node_name: # static placed component, do not touch
                continue

        current_node_placed = components_state[comp_name]['node_placed']
        if current_node_placed is not None:
            # component is placed, move it to another
            available_nodes = [node for node in system_description['MLSysOpsCluster']['nodes'] if node != current_node_placed]
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

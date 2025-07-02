"""Plugin module for custom policies - notify function."""
from __future__ import print_function
import copy
import logging
import inspect

logger = logging.getLogger(__name__)

def get_curr_container_img(comp_name, context):
    for comp in context['spec']['components']:
        if comp_name != comp['metadata']['name']:
            continue
        container = comp.get("containers")[0]['image']
        return container

def initialize():
    initialContext = {
        "id": "test_case_1",
        "telemetry": {
            "metrics": ["node_load1"],
            "system_scrape_interval": "2s"
        },
        "mechanisms": ["fluidity"],
        "packages": [],
        "configuration": {
            "analyze_interval": "5s"
        },
        "scope": "application",
        "core": True,
        "latest_timestamp": None
    }

    return initialContext

""" Plugin function to implement the initial deployment logic.
"""
def initial_plan(context, app_desc, system_desc):
    context['name'] = app_desc['name']
    context['spec'] = app_desc['spec']

    if 'initial_deployment_finished' not in context:
        context['initial_deployment_finished'] = True

    context['component_names'] = []
    plan = {}

    for component in app_desc['spec']['components']:
       
        comp_name = component['metadata']['name']
        logger.info('component %s', comp_name)
        context['component_names'].append(comp_name)
        node_placement = component.get("node_placement", None)
        if node_placement:
            node_name = node_placement.get("node", None)
            if node_name:
                plan[comp_name] = [{'action': 'deploy', 'host': node_name}]

    return plan, context


async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    application = application_description[0]
    adaptation = False
    
    if 'initial_deployment_finished' not in context:
        logger.info('initial deployment not finished')
        adaptation = True
    else:
        if context['spec'] != application['spec']:    
            logger.info('App has changed. Will trigger plan')
            adaptation = True

    return adaptation, context


async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    plan_result = {}
    plan_result['deployment_plan'] = {}
    application = application_description[0]
    description_changed = False


    if 'initial_deployment_finished' not in context:
        initial_plan_result, new_context = initial_plan(context, application, system_description)
        if initial_plan_result:
            plan_result['deployment_plan'] = initial_plan_result
            plan_result['deployment_plan']['initial_plan'] = True
    elif application['spec'] != context['spec']:
        logger.info(f'APPLICATION DESCRIPTION HAS CHANGED')
        description_changed = True
        context['spec'] = application['spec']

    if plan_result['deployment_plan']:
        plan_result['name'] = context['name']
       
    new_plan = {
        "fluidity": plan_result
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context

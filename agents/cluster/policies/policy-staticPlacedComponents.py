"""Plugin module for custom policies - notify function."""
from __future__ import print_function
import copy
import logging
import inspect

logger = logging.getLogger(__name__)
counter = 0

def get_curr_container_img(comp_name, context):
    for comp in context['spec']['components']:
        if comp_name != comp['Component']['name']:
            continue
        container = comp.get("containers")[0]['image']
        return container

def initialize():
    print(f"Initializing policy {inspect.stack()[1].filename}")

    initialContext = {
        "telemetry": {
            "metrics": ["node_load1"],
            "system_scrape_interval": "1s"
        },
        "mechanisms": [
            "CPUFrequencyConfigurator"
        ],
        "packages": [

        ],
        "configuration": {
            "analyze_interval": "1s"
        },
        "scope": "application",
        "core": True,
        "latest_timestamp": None,
        "initial_deployment_finished": False
    }

    return initialContext

""" Plugin function to implement the initial deployment logic.
"""
def initial_plan(context, app_desc, system_desc):
    logger.info('initial deployment phase ', app_desc)

    # context['nodes'] = dict(system_desc['nodes'])
    context['name'] = app_desc['name']
    context['spec'] = app_desc['spec']
    context['initial_deployment_finished'] = True
    context['component_names'] = []
    #logger.info('context %s', context)
    plan = {}

    for component in app_desc['spec']['components']:
        #logger.info('component %s', component)
        comp_name = component['Component']['name']
        context['component_names'].append(comp_name)
        node_placement = component.get("nodePlacement")
        if node_placement:
            node_name = node_placement.get("node")
            if node_name and node_name != "*":
                plan[comp_name] = [{'action': 'deploy', 'host': node_name}]
        else:
            logger.error('Did not find component-to-node mapping. Empty plan.')
            plan[comp_name] = [{'action': 'deploy', 'host': 'csl-vader'}]
    # plan['tractor-app'] = [{'action': 'deploy', 'host': 'csl-vader'}]
    # plan['drone-app'] = [{'action': 'deploy', 'host': 'csl-alveo'}]
    global counter
    counter = 1
    #logger.info('Initial plan %s', plan)
    return plan, context


def analyze(context, application_description, system_description, current_plan, telemetry, ml_connector):
    logger.info('Analyze has current deployment %s', current_plan)
    application = application_description[0]
    adaptation = False
    # NOTE: Fix analyze, it does not receive the updated app description
    #return True, context

    if not context['initial_deployment_finished']:
        logger.info('initial deployment not finished')
        adaptation = True
    else:
        #logger.info('context %s', context['spec'])
        #logger.info('application %s', application['spec'])
        if 'spec' in application:
            curr_app = application['spec']
        else:
            curr_app = application
        if context['spec'] != curr_app:    
            logger.info('App has changed. Will trigger plan')
            adaptation = True
    # Not applicable    
    return adaptation, context


def plan(context, application_description, system_description, current_plan, telemetry, ml_connector, available_assets):    # Not applicable
    # plan_result = {
    #     'name': None,
    #     'deployment_plan': {}
    # }
    plan_result = {}
    application = application_description[0]
    #logger.info('application_description %s', application)
    
    if 'initial_deployment_finished' in context and context['initial_deployment_finished'] == False:
        initial_plan_result, new_context = initial_plan(context, application, system_description)
        if initial_plan_result:
            plan_result['deployment_plan'] = initial_plan_result
            plan_result['deployment_plan']['initial_plan'] = True
    else:
        #logger.info('Plan: application %s', application)

        description_changed = False
        if 'spec' in application:
            iterate = application['spec']
        else:
            iterate = application
        # NOTE: After the app modification, the new app does not have the form
        # name: ..., spec: ...
        # but it only contains spec's contents. Must fix this.
        for component in iterate['components']:
            comp_name = component['Component']['name']
            node_placement = component.get("nodePlacement")
            if node_placement:
                node_name = node_placement.get("node")
            containers = component.get("containers")
            #logger.info('containers %s', containers)
            #logger.info('containers image %s', containers[0]['image'])
            curr_img = get_curr_container_img(comp_name, context)
            logger.info('Current img: %s', curr_img)
            logger.info('Current img: %s',  containers[0]['image'])
            if containers[0]['image'] != curr_img:
                new_img = containers[0]['image']
                logger.info('Container image updated for component %s. New img: %s', comp_name, new_img)
                plan_result['deployment_plan'] = {}
                plan_result['deployment_plan'][comp_name] = [{'action': 'change_img', 'new_img': new_img, 'host': node_name}]
                description_changed = True
        if description_changed:
            logger.info('Plan updating the app description')
            if 'spec' in application:
                context['spec'] = application['spec']
            else:
                context['spec'] = application
            plan_result['deployment_plan']['initial_plan'] = False
        new_context = context
    
    if plan_result:
        plan_result['name'] = context['name']
       
    new_plan = {
        "fluidity": plan_result
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, new_context

"""Plugin module for custom policies - notify function."""
from __future__ import print_function

import inspect
import random
import re
import time
from mlsysops.logger_util import logger

def initialize():
    """
    Initializes and returns the initial context configuration for the policy. This initial
    context includes telemetry settings, plan mechanisms, required packages, configuration intervals,
    and the scope of the policy.

    Returns:
        dict: A dictionary containing the initial context configuration for an application.
    """
    initial_context = {
        "telemetry": {
            "metrics": [],
            "system_scrape_interval": "5s"
        },
        "mechanisms": ["fluidity"],
        "packages": [],
        "configuration": {
            "analyze_interval": "1s"
        },
        "scope": "application",
    }

    return initial_context



def initial_plan(context, app_desc, system_description, components_state):
    """
    Generates an initial deployment plan for application components in a distributed system.

    The function creates an initial deployment plan for application components by analyzing
    the application description, system description, and the current state of components.
    It determines the placement of each component and adds actions to the plan based on
    predefined criteria such as existing placements or static placement specifications.

    Parameters:
        context (dict): A dictionary used to store and update deployment-related information
            during the planning process.
        app_desc (dict): The application description, which includes details about the
            application name, specifications, and the components to be deployed.
        system_description (dict): The system description, outlining the infrastructure
            details such as nodes available in the deployment cluster.
        components_state (dict): The current state of each component, including whether
            it has already been deployed and on which node.

    Returns:
        tuple: A tuple containing the deployment plan and the updated context.
            - plan (dict): The generated deployment plan mapping component names to
              a list of deployment actions (e.g., deploy on a specified host).
            - context (dict): The updated context with added deployment information such
              as component names and their placements.
    """
    logger.info('initial deployment phase ', app_desc)

    context['name'] = app_desc['name']
    context['spec'] = app_desc['spec']
    context['component_names'] = []
    plan = {}

    # TODO: add filtering, based on system description and application component requirements
    context["current_placement"] = random.choice(system_description['MLSysOpsCluster']['nodes'])

    for component in app_desc['spec']['components']:
        comp_name = component['metadata']['name']
        context['component_names'].append(comp_name)
        node_placement = component.get("node_placement")
        if node_placement:
            node_name = node_placement.get("node", None)
            if node_name:
                logger.info(f'Component {comp_name} is static placed. No initial plan needed')
                continue
        if components_state[comp_name]['node_placed'] is not None:
            logger.info(f'Component {comp_name} already placed in {components_state[comp_name]["node_placed"]}. No initial plan needed')
            continue
        # Initial deployment needed for this component
        plan[comp_name] = [{'action': 'deploy', 'host': context["current_placement"]}]
    return plan, context

async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    components_state = mechanisms['fluidity']['state']['applications'][application_description[0]['name']]['components']

    for component in application_description[0]['spec']['components']:
        comp_name = component['metadata']['name']
        node_placement = component.get("node_placement")
        if node_placement:
            node_name = node_placement.get("node", None)
            if node_name:
                logger.info('Found node name - static placed. Will continue')
                continue
        if components_state[comp_name]['node_placed'] is not None:
            logger.info(f'Component {comp_name} already placed in {components_state[comp_name]["node_placed"]}. No initial plan needed')
            continue
        
        # Even if one component is not placed, return true
        context['configuration']['analyze_interval'] = "30s" # increase it, to wait for changes to take effect
        return True, context

    context['configuration']['analyze_interval'] = "1s"  # revert back to faster analyzer internval
    return False, context



async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):

    plan_result = {}
    plan_result['deployment_plan'] = {}
    application = application_description[0]
    
    # check if in the state the client app has been placed
    # use fluidity state for that
    components_state = mechanisms['fluidity']['state']['applications'][application_description[0]['name']]['components']

    initial_plan_result, new_context = initial_plan(context, application, system_description,components_state)
    if len(initial_plan_result.keys()) > 0:
        # in case an initial plan exists for at least one component, we cannot send non-initial plan payload
        plan_result['deployment_plan'] = initial_plan_result
        plan_result['deployment_plan']['initial_plan'] = True

    if plan_result:
        plan_result['name'] = context['name']

    new_plan = {
        "fluidity": plan_result,
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context

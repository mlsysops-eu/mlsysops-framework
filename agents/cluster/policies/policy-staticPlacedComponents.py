"""Plugin module for custom policies - notify function."""
from __future__ import print_function
import copy
import logging

from fluidityapp_util import FluidityAppInfoDict, FluidityCompInfoDict, FluidityNodeInfoDict, FluidityPolicyAppInfoDict
from mlstelemetry import MLSTelemetry


mlsClient = MLSTelemetry("fluidity_mechanism", "ubiwhere_policy")

logger = logging.getLogger(__name__)

def init():
    pass

""" Plugin function to implement the initial deployment logic.
"""
def initial_plan(app_desc, system_desc):
    logger.info('initial deployment phase')
    context = copy.deepcopy(FluidityPolicyAppInfoDict)

    context['nodes'] = dict(system_desc['nodes'])
    context['name'] = app_desc['name']
    context['spec'] = app_desc['spec']
    context['component_names'] = []

    plan = {}

    for component in app_desc['spec']['components']:
        comp_name = component['Component']['name']
        context['component_names'].append(comp_name)
        node_placement = component.get("nodePlacement")
        if node_placement:
            node_name = node_placement.get("node")
            if node_name and node_name != "*":
                plan[comp_name] = [{'name': node_name, 'status': 'PENDING'}]
        else:
            logger.error('Did not find component-to-node mapping. Empty plan.')
    return plan, context


def analyze_status(app_desc, nodes, context, system_metrics, updated_nodes, curr_deployment):
    # Not applicable

    return {}, context


def re_plan(old_app_desc, new_app_desc, context, curr_deployment):
    # Not applicable

    return {}, context

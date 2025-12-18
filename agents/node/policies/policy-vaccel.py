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
from mlstelemetry import MLSTelemetry

mlsClient = MLSTelemetry("policy", "policy_vaccel")

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
    initialContext = {
        "telemetry": {
            "metrics": ["vaccel_dynamicity_enabled","vaccel_dynamicity_threshold", "processing_time", "inference_time"],
            "system_scrape_interval": "1s"
        },
        "mechanisms": [
            "vaccel"
        ],
        "packages": [],
        "configuration": {
            "analyze_interval": "5s"
        },
        "latest_timestamp": None,
        "core": False,
        "scope": "global",
        "curr_comp_idx": 0,
        "current_placement": None,
        "initial_deployment_finished": False,
        "moving_interval": "600s",
        "dynamic_placement_comp": None,
        "threshold_epsilon": 50
    }

    return initialContext


async def get_metric(metric_name, telemetry):
    # Get latest values from telemetry data
    component_measured_metric = None
    try:
        latest_telemetry_df = await telemetry['query'](latest=True)
        # latest_telemetry_df = telemetry['query'](latest=True)
        component_measured_metric = latest_telemetry_df[metric_name].values[0]
        logger.debug(f"metric {metric_name} measurement {component_measured_metric} ")
    except Exception as e:
        logger.error(f"Failed to get metric {metric_name}")

    return component_measured_metric

async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    is_enabled = await get_metric("vaccel_dynamicity_enabled",telemetry)
    threshold = await get_metric("vaccel_dynamicity_threshold",telemetry)
    processing_time = await get_metric("processing_time",telemetry)
    inference_time = await get_metric("inference_time",telemetry)

    if is_enabled and processing_time > threshold:
        logger.info(f"Processing time {processing_time} is above threshold {threshold}")
        return True, context

    if is_enabled and processing_time < (threshold - context['threshold_epsilon']):
        logger.info(f"Processing time {processing_time} is below threshold {threshold} with epsilon {context['threshold_epsilon']}")
        return True, context

    logger.info(f"Processing time {processing_time} is below threshold {threshold}")
    return False, context


async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):

    threshold = await get_metric("vaccel_dynamicity_threshold",telemetry)
    processing_time = await get_metric("processing_time",telemetry)
    inference_time = await get_metric("inference_time",telemetry)
    logger.info(f"Processing time {processing_time} and threshold {threshold}")

    current_backend = mechanisms['vaccel']['state']['backend']
    current_options = mechanisms['vaccel']['options']
    logger.info(f"Current backend {current_backend} and options {current_options}")

    if processing_time > threshold:
        plan_result = {
            "backend": "vaccel-bf"
        }


    if processing_time < (threshold - context['threshold_epsilon']):
        plan_result = {
            "backend": "vaccel-cpu"
        }

    if current_backend == plan_result['backend']:
        return {},context
    new_plan = {
        "vaccel": plan_result
    }

    logger.info('plan: New plan %s', new_plan)

    return new_plan, context

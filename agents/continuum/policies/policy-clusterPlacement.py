"""Plugin module for custom policies - notify function."""
from __future__ import print_function

import inspect
import random
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
    initialContext = {
        "telemetry": {
            "metrics": ["cluster"],
            "system_scrape_interval": "1s"
        },
        "mechanisms": ["clusterPlacement"],
        "packages": [],
        "configuration": {
            "analyze_interval": "5s"
        },
        "latest_timestamp": None,
        "core": True,
        "scope": "application",
        "current_placement": "uth-prod-cluster",
        "first_run": True
    }

    return initialContext


async def analyze(context, application_description, system_description, current_plan, telemetry, ml_connector):
    # a simple policy that periodically changes the frequency of the node
    # Analyze
    print("Called analyze of relocation ", context)
    current_timestamp = time.time()

    if not context['first_run']:
        return False, context
    # The first time called
    if context['latest_timestamp'] is None:
        context['latest_timestamp'] = current_timestamp
        return False, context

    # All the next ones, get it
    analyze_interval = parse_analyze_interval(context['configuration']['analyze_interval'])
    if current_timestamp - context['latest_timestamp'] > analyze_interval:
        context['latest_timestamp'] = current_timestamp
        context['first_run'] = False
        return True, context

    return False, context


async def plan(context, application_description, system_description, current_plan, telemetry, ml_connector, available_assets):



    #Inference should dictate where to put the app description  and create the message new_plan
    cluster_to_move = random.choice(["cluster1", "uth-prod-cluster"])
    logger.info('App_desc received in the plan  %s', application_description)
    new_plan = {
        "clusterPlacement": {"action": {
            "component": cluster_to_move
        },
            "app": application_description}
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context

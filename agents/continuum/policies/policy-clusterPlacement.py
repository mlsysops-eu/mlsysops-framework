"""Plugin module for custom policies - notify function."""
from __future__ import print_function

import inspect
import re
import time
import logging

logger = logging.getLogger(__name__)


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
            "metrics": [],
            "system_scrape_interval": "1s"
        },
        "mechanisms": [],
        "packages": [],
        "configuration": {
            "analyze_interval": "30s"
        },
        "latest_timestamp": None,
        "core": False,
        "scope": "application"
    }

    return initialContext


def analyze(context, application_description, system_description, current_plan, telemetry, ml_connector):
    # a simple policy that periodically changes the frequency of the node
    # Analyze
    print("Called analyze of relocation ", context)
    current_timestamp = time.time()

    # The first time called
    if context['latest_timestamp'] is None:
        context['latest_timestamp'] = current_timestamp
        return False, context

    # All the next ones, get it
    analyze_interval = parse_analyze_interval(context['configuration']['analyze_interval'])
    print(f"{current_timestamp} - {context['latest_timestamp']}  = {current_timestamp - context['latest_timestamp']} with interval {analyze_interval}")
    if current_timestamp - context['latest_timestamp'] > analyze_interval:
        context['latest_timestamp'] = current_timestamp
        return True, context

    return False, context



def plan(context, application_description, system_description, current_plan, telemetry, ml_connector, available_assets):

    new_plan = {
        "clusterPlacement": {"client-app": "uht-prod-cluster", "server-app": "uht-prod-cluster"},
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context

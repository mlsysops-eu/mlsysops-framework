"""Plugin module for custom policies - notify function."""
from __future__ import print_function

import inspect
import pprint
import copy
import json
import logging
import os
import queue
import sys
import threading
import time
import random

from mlstelemetry import MLSTelemetry

mlsClient = MLSTelemetry("fluidity_mechanism", "ubiwhere_policy")



def initialize():
    print(f"Initializing policy {inspect.stack()[1].filename}")


""" Plugin function to implement the initial deployment logic.
"""
def initial_plan(app_desc, cores):
    plan = []
    context = []
    return plan, context


def analyze(context, component_spec, application_targets, telemetry):
    analysis_result = True
    print("Called analyze")
    return analysis_result, context



def re_plan(context, component_spec, application_targets, telemetry, mechanisms):
    print("Called replan")

    return {
        "clusterPlacement" :
            {"componentX": "clusterP",
             "componentY": "clusterN"}
    }
    return mechanisms, context

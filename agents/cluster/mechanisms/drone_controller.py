#   Copyright (c) 2025. MLSysOps Consortium
#   #
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#   #
#       http://www.apache.org/licenses/LICENSE-2.0
#   #
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#  #
#  #

import json
import traceback
# from mlsysops.logger_util import logger
from mlsysops import MessageEvents
import mlsysops
from mlsysops.logger_util import logger
from DroneControllerAPI import ControllerAPI
import os
drone_ctrl_client = ControllerAPI.ControllerAPI(os.getenv("DRONE_CONTROLLER_ENDPOINT","100.64.0.2"),1980)

queues = {"inbound": None, "outbound": None}
# AUG ADDITIONS -- START
from mlstelemetry import MLSTelemetry
mlsClient = MLSTelemetry("drone_controller_mechanism", "aug_cluster_mechanism")

# drone command codes
DRONE_IDLE = 10
UI_START_FOLLOW = 11
UI_STOP_FOLLOW = 12

DRONE_CONTROLLER_DISABLE = os.getenv("DRONE_CONTROLLER_DISABLE", "false")

async def send_last_drone_cmd(cmd):
    mlsClient.pushMetric(f'fluidity_drone_command', "gauge", cmd)

# TODO: REMOVE! This is for the desk setup testing only.
async def start_follow_tractor():
    try:
        status=drone_ctrl_client.StartFollow(10,10)
        logger.info(status)
    except Exception as e:
        logger.error(str(e))
    await send_last_drone_cmd(UI_START_FOLLOW)

# TODO: REMOVE! This is for the desk setup testing only.
async def stop_follow_tractor():
    try:
        status=drone_ctrl_client.StopFollow()
        logger.info(status)
    except Exception as e:
        logger.error(str(e))
    await send_last_drone_cmd(UI_STOP_FOLLOW)


def initialize(inbound_queue=None, outbound_queue=None, agent_state=None):
    global fluidity_mechanism_instance

    logger.debug("Initializing fluidity mechanism")

    queues["inbound"] = inbound_queue
    queues["outbound"] = outbound_queue


async def apply(plan):
    try:
        # AUG ADDITIONS -- START
        if "start_follow_tractor" in plan and plan["start_follow_tractor"]:
            logger.info('Sending start follow tractor msg to drone controller.')
            mlsClient.pushLogInfo('DRONE_COMMAND: START FOLLOW')
            # NOTE: We should wait until the drone controller's status is 'FOLLOWING' before we deploy the drone app.
            # We need this because we do not want the drone app to send invalid results based on an irrelevant region.
            if DRONE_CONTROLLER_DISABLE.lower() == "false":
                await start_follow_tractor()
        elif "stop_follow_tractor" in plan and plan["stop_follow_tractor"]:
            logger.info('Sending stop follow tractor msg to drone controller.')
            mlsClient.pushLogInfo('DRONE_COMMAND: STOP FOLLOW')
            if DRONE_CONTROLLER_DISABLE.lower() == "false":
                await stop_follow_tractor()
    except Exception as e:
        logger.debug("Error in sending message to fluidity")
        print(traceback.format_exc())

    return False

def get_state():
    return {}


def get_options():
    return {}
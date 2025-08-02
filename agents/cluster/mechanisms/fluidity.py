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

import asyncio
import json
import traceback
from asyncio import CancelledError
from dataclasses import dataclass, field
from typing import Dict
from pydantic import ValidationError

import fluidity.controller as fluidity_controller

from fluidity.plan_payload import FluidityPlanPayload
from fluidity.internal_payload import FluidityEvent

# from mlsysops.logger_util import logger
from mlsysops import MessageEvents
import mlsysops
from mlsysops.logger_util import logger

queues = {"inbound": None, "outbound": None}


class FluidityMechanism:

    state: Dict = field(default_factory=dict)
    inbound_queue = None
    outbound_queue = None
    internal_queue_inbound = None
    internal_queue_outbound = None
    state = None
    fluidity_proxy_plans = {}

    def __init__(self, mlsysops_inbound_queue=None, mlsysops_outbound_queue=None, agent_state=None):
        self.inbound_queue = mlsysops_inbound_queue
        self.outbound_queue = mlsysops_outbound_queue
        self.state = {"applications": {}, "nodes": {}, "cluster": {}}

        self.internal_queue_inbound = asyncio.Queue()
        self.internal_queue_outbound = asyncio.Queue()

        # Reverse the in- and out-, to make it more clear.
        asyncio.create_task(fluidity_controller.main(outbound_queue=self.internal_queue_inbound,
                                                     inbound_queue=self.internal_queue_outbound,
                                                     cluster_description=agent_state.configuration.system_description))

        asyncio.create_task(self.internal_message_listener())
        asyncio.create_task(self.mlsysops_message_listener())

    async def mlsysops_message_listener(self):

        while True:
            try:
                message = await self.outbound_queue.get()

                event = message.get("event", None) # message_to_fluidity
                logger.debug(f"Received message from MLS agent: {event}")

                if event and event == MessageEvents.MESSAGE_TO_FLUIDITY.value:
                    fluidity_payload = message.get("payload", {})
                    fluidity_internal_event = fluidity_payload.get("event", None) # fluidity_plan_submitted
                    fluidity_internal_payload = fluidity_payload.get("payload", {})
                    origin_node = fluidity_payload.get("node", None)
                    match fluidity_internal_event:
                        case MessageEvents.FLUIDITY_INTERNAL_PLAN_SUBMITTED.value:
                            plan_payload = fluidity_internal_payload.get("payload", {})
                            plan_uid = plan_payload.get("plan_uid", None)
                            if plan_uid:
                                self.fluidity_proxy_plans[plan_uid] = {"node": origin_node,
                                                                       "plan": fluidity_internal_event}
                                logger.debug(f"Received plan submitted from fluidity proxy: {plan_uid}")
                                await self.internal_queue_outbound.put(fluidity_internal_payload)
                        case _:
                            logger.error(f"Unknown fluidity internal event: {fluidity_internal_event}")

            except CancelledError:
                logger.debug("Cancelled error in mlsysops_message_listener")
                break

    async def internal_message_listener(self):

        messages_to_forward = [
            MessageEvents.APP_CREATED.value,
            MessageEvents.APP_REMOVED.value,
            MessageEvents.APP_DELETED.value,
            MessageEvents.APP_UPDATED.value,
            MessageEvents.APP_SUBMIT.value,
            MessageEvents.COMPONENT_PLACED.value,
            MessageEvents.COMPONENT_REMOVED.value,
        ]

        while True:
            try:
                # Listen to fluidity messages
                message = await self.internal_queue_inbound.get()

                # Log or save message for debugging
                with open("fluidity_dump.json", "w") as file:
                    file.write(json.dumps(message, skipkeys=True, indent=4, default=str, ensure_ascii=False, sort_keys=True,
                                          separators=(',', ': ')))
                    file.write(",\n")  # Ensure a newline is added after the content

                event = message.get("event")
                if not event:
                    continue

                # Validate event payload
                try:
                    # Validate the payload using Pydantic
                    FluidityEvent(**message)
                except ValidationError as e:
                    # Print validation errors if any
                    logger.error(f"Plan Validation failed: {e}")
                    continue

                if event in messages_to_forward:
                    # forward the message to MLS agent
                    await self.inbound_queue.put(message)

                # Handle specific internal messages
                if event == MessageEvents.PLAN_EXECUTED.value:
                    # check if it originated from a node agent
                    data = message.get("payload", {})
                    plan_uid = data.get("plan_uid", None)
                    if plan_uid:
                        if plan_uid in self.fluidity_proxy_plans:
                            logger.debug(f"Forwarding plan executed message to fluidity proxy")
                            # Forward to node
                            await self.inbound_queue.put({
                                "event": MessageEvents.MESSAGE_TO_FLUIDITY_PROXY.value,
                                "node": self.fluidity_proxy_plans[plan_uid]["node"],
                                "payload": {
                                    "event": MessageEvents.FLUIDITY_INTERNAL_PLAN_UPDATE.value,
                                    "payload": message
                                }
                            })
                            logger.test(f"|2| Fluidity mechanism received planuid:{plan_uid} status:Node forward to MLSNodeAgent:{self.fluidity_proxy_plans[plan_uid]['node']}")
                            del self.fluidity_proxy_plans[plan_uid]
                        else:
                            # forward the message to MLS agent
                            await self.inbound_queue.put(message)
                            logger.test(f"|2| Fluidity mechanism received planuid:{plan_uid} forward to status:MLSClusterAgent")


                elif event == MessageEvents.CLUSTER_SYSTEM_DESCRIPTION_SUBMITTED.value:
                    payload = message.get("payload", {})
                    nodes = payload.get("spec", {}).get("nodes", [])
                    cluster_description = {
                        "name": payload.get("name"),
                        "spec": payload.get("spec"),
                        "nodes": nodes,  # Populate nodes
                    }

                    # Update cluster state
                    self.state["cluster"]["description"] = cluster_description

                    # Merge new nodes into current state without overwriting
                    for node in nodes:
                        self.state["nodes"].setdefault(node, {})  # Ensure node exists in state with default empty dict
                    logger.debug(f"Updated cluster state")

                elif event == MessageEvents.KUBERNETES_NODE_ADDED.value:
                    # Process the kubernetes_node_added event
                    payload = message.get("payload", {})
                    node_name = payload.get("name")
                    node_spec = payload.get("spec", "{}")
                    node_status = node_spec.get("status", {})

                    # Determine readiness state
                    conditions = node_status.get("conditions", [])
                    ready_state = next(
                        (condition.get("status") for condition in conditions if condition.get("type") == "Ready"),
                        "Unknown"
                    )

                    # Parse resources
                    resources = {
                        "capacity": node_status.get("capacity", {}),
                        "allocatable": node_status.get("allocatable", {}),
                    }

                    # Update or merge with the node state
                    if node_name:
                        self.state["nodes"].setdefault(node_name, {})  # Ensure the node exists with default empty dict
                        self.state["nodes"][node_name].update({
                            "ready": ready_state,
                            "resources": resources,
                        })
                        logger.debug(f"Updated state for node {node_name}")
                    else:
                        logger.warning("Node name missing in kubernetes_node_added event payload.")

                elif event == MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMITTED.value:
                    payload = message.get("payload", {})
                    node_spec = payload.get("spec", {})
                    node_name = payload.get("name", "")

                    # Ensure the node exists in the state and update only the 'spec' field
                    if node_name:
                        self.state["nodes"].setdefault(node_name, {})
                        self.state["nodes"][node_name].update({
                            "spec": node_spec
                        })
                        logger.debug(f"Updated node system description for '{node_name}'")
                    else:
                        logger.warning("Node name missing in node_system_description_submitted event payload.")

                elif event == MessageEvents.APP_CREATED.value:
                    # Handle application created event
                    payload = message.get("payload", {})
                    app_name = payload.get("name")
                    app_spec = payload.get("spec", {})
                    components = app_spec.get("components", [])
                    global_satisfaction = app_spec.get("global_satisfaction", {})

                    if app_name:
                        # Build or merge components into the application
                        components_data = {}
                        for component in components:
                            metadata = component.get("metadata", {})
                            metadata_name = metadata.get("name")
                            metadata_uid = metadata.get("uid")
                            qos_metrics = component.get("qos_metrics", [])
                            if metadata_name and metadata_uid:
                                components_data[metadata_name] = {
                                    "uid": metadata_uid,
                                    "qos_metrics": qos_metrics,
                                    "state": "Unknown",
                                    "node_placed": None,
                                }

                        # Update the applications state
                        self.state["applications"].setdefault(app_name, {})
                        self.state["applications"][app_name].update({
                            "spec": app_spec,
                            "components": components_data,
                            "global_metrics": global_satisfaction
                        })
                        logger.debug(f"Updated state for application '{app_name}'")
                    else:
                        logger.warning("Application name missing in application_created event payload.")

                elif event == MessageEvents.APP_DELETED.value:
                    # Handle application created event
                    payload = message.get("payload", {})
                    app_name = payload.get("name")
                    del self.state["applications"][app_name]

                elif event == MessageEvents.POD_MODIFIED.value:
                    # Handle pod modified event
                    payload = message.get("payload", {})
                    pod_spec = payload.get("spec", "{}")
                    pod_metadata = pod_spec.get("metadata", {})
                    pod_labels = pod_metadata.get("labels", {})
                    pod_state = pod_spec.get("status", {}).get("phase", "Unknown")
                    node_name = pod_spec.get("spec", {}).get("node_name", None)

                    # Extract labels
                    app_name = pod_labels.get("mlsysops.eu/app")
                    component_name = pod_labels.get("mlsysops.eu/component")
                    component_uid = pod_labels.get("mlsysops.eu/componentUID")

                    if app_name and app_name in self.state["applications"] and component_name:
                        # Update the application component state
                        app = self.state["applications"][app_name]
                        components = app.get("components", {})

                        components.setdefault(component_name, {}).update({
                            "labels": pod_labels,
                            "state": pod_state,
                            "node_placed": node_name
                        })

                        # Test log
                        logger.test(
                            f"|3| Fluidity mechanism planuid:{pod_labels.get('mlsysops.eu/planUID','-')} pod modification status:Success")

                        # Update the node's state
                        if node_name:
                            self.state["nodes"].setdefault(node_name, {})
                            self.state["nodes"][node_name].setdefault("components", {})
                            self.state["nodes"][node_name]["components"][component_name] = {
                                "uid": component_uid,
                                "state": pod_state,
                                "labels": pod_labels,
                                "app_name": app_name,
                                "component_spec": pod_spec["spec"],
                            }
                            node_state_touched = node_name
                            await self.inbound_queue.put({
                                "event": MessageEvents.MESSAGE_TO_FLUIDITY_PROXY.value,
                                "node": node_name,
                                "payload": self.state["nodes"][node_name]
                            })
                            logger.debug(f"Updated node '{node_name}' with component '{component_name}'")
                        else:
                            logger.warning(f"Node name is missing for component '{component_name}' in app '{app_name}'.")
                    else:
                        logger.warning("Invalid or missing app/component labels in pod_modified event payload.")
            except CancelledError:
                logger.debug("Cancelled error in internal_message_listener")
                break


fluidity_mechanism_instance = None


def initialize(inbound_queue=None, outbound_queue=None, agent_state=None):
    global fluidity_mechanism_instance

    logger.debug("Initializing fluidity mechanism")

    queues["inbound"] = inbound_queue
    queues["outbound"] = outbound_queue

    fluidity_mechanism_instance = FluidityMechanism(inbound_queue, outbound_queue, agent_state)


async def apply(plan):
    global fluidity_mechanism_instance

    try:
        # Validate the payload using Pydantic
        FluidityPlanPayload(**plan)
    except ValidationError as e:
        # Print validation errors if any
        logger.error(f"Plan Validation failed: {e}")

        msg = {
            "event": MessageEvents.PLAN_EXECUTED.value,
            'payload': {
                'name': plan['plan_uid'],
            }
        }

        # forward the message to MLS agent
        await fluidity_mechanism_instance.inbound_queue.put(msg)
        logger.test(f"|1| Fluidity mechanism planuid:{plan['plan_uid']} failed validation status:Failed")
        logger.test(plan)
        logger.test(e)
        return

    msg = {
        "event": MessageEvents.PLAN_SUBMITTED.value,
        "payload": plan
    }
    try:
        await fluidity_mechanism_instance.internal_queue_outbound.put(msg)
        logger.test(f"|1| Fluidity mechanism forwarded planuid:{plan['plan_uid']} to Fluidity status:True")

    except Exception as e:
        logger.error("Error in sending message to fluidity")
        logger.exception(traceback.format_exc())

    return False


async def send_message(msg):
    global fluidity_mechanism_instance

    logger.debug(f"Sending message to fluidity {msg}")
    try:
        await fluidity_mechanism_instance.internal_queue_outbound.put(msg)
    except Exception as e:
        logger.error("Error in sending message to fluidity")
        logger.exception(traceback.format_exc())


def get_state():
    global fluidity_mechanism_instance
    if fluidity_mechanism_instance is not None:
        return fluidity_mechanism_instance.state
    else:
        return {}


def get_options():
    global fluidity_mechanism_instance
    return {}
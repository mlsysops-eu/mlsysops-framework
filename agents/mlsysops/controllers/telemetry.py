#  Copyright (c) 2025. MLSysOps Consortium
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import json
import os
import traceback
from unittest import case

import asyncio

import mlsysops.events
import yaml
from jinja2 import Template, PackageLoader, Environment, select_autoescape

from mlsysops.controllers.base import BaseController
from mlsysops.data.state import MLSState
from mlsysops.tasks.monitor import MonitorTask

from mlsysops.logger_util import logger

from .libs.otel_pods import create_otel_pod, create_svc, delete_otel_pod, remove_service, deploy_node_exporter_pod, \
    delete_node_exporter_pod


class TelemetryController(BaseController):

    def __init__(self, agent,monitor_task: MonitorTask, agent_state: MLSState = None):

        logger.debug("Initializing telemetry controller...")
        self.agent = agent
        self.monitor_task = monitor_task
        self.agent_state = agent_state
        self.otel_pod_list = []
        self.node_exporter_pod_list = []


    def __del__(self):
        logger.debug("Telemetry controller destroyed.")
        match self.agent.state.configuration.continuum_layer:
            case "none":
                logger.debug("No target level configuration applied.")
                return
            case "cluster":
                for pod_entry in self.otel_pod_list:
                    try:
                        delete_otel_pod(pod_entry['node'])
                        remove_service()
                    except Exception as e:
                        logger.error(f"Failed to remove OTEL pod: {pod_entry}, error: {e}")
                logger.debug("Removing node exporter pods......................................")
                for pod_entry in self.node_exporter_pod_list:
                    logger.debug(f"Removing node exporter pod: {pod_entry}")
                    try:
                        delete_node_exporter_pod(pod_entry['node'])
                    except Exception as e:
                        logger.error(f"Failed to remove node exporter pod: {pod_entry}, error: {e}")
            case "node":
                    # Send the parsed content to the cluster
                    # TODO spade seems to shutdown - no message goes out.
                    payload = {"node": self.agent.state.hostname}
                    asyncio.create_task(self.agent.send_message_to_node(self.agent_state.configuration.cluster,mlsysops.events.MessageEvents.OTEL_REMOVE.value,payload))
            case "continuum":
                delete_otel_pod(self.agent.state.hostname)
                remove_service()
                pass


    async def apply_configuration_telemetry(self):
        # add metrics from the configuration file
        if (self.agent_state.configuration is not None
                and
                self.agent_state.configuration.default_telemetry_metrics != "None"):
            # enable system metrics with current config for monitor tasks
            for metric_name in self.agent_state.configuration.default_telemetry_metrics:
                logger.debug(f"Adding metric {metric_name} to monitor task.")
                await self.monitor_task.add_metric(metric_name)


    async def initialize(self):
        """
        Reads the otel-config.yaml file, parses its content, and sends it to the cluster.
        """
        try:
            parsed_otel_config = ""

            # Define the loader for Jinja environment
            loader = PackageLoader("mlsysops", "templates")
            env = Environment(
                loader=loader,
                autoescape=select_autoescape(enabled_extensions=("j2"))
            )

            # Load the template
            template = env.get_template("otel-config.yaml.j2")

            # Log the parsed content (for debugging purposes)
            logger.debug(f"Parsed OTEL configuration for level {self.agent.state.configuration.continuum_layer}")

            match self.agent.state.configuration.continuum_layer:
                case "none":
                    logger.debug("No target level configuration applied.")
                    return
                case "cluster":
                    logger.debug("Applying cluster default telemetry configuration.")
                    if self.agent_state.configuration.otel_deploy_enabled:
                        # Render the template with the `otlp_export_endpoint`
                        otlp_export_endpoint_enabled = os.getenv("MLS_OTEL_HIGHER_EXPORT", "ON")
                        if otlp_export_endpoint_enabled == "ON":
                            otlp_export_endpoint = f'{os.getenv("EJABBERD_DOMAIN","127.0.0.1")}:{os.getenv("MLS_OTEL_CONTINUUM_PORT","43170")}'
                        else:
                            otlp_export_endpoint = None
                        parsed_otel_config = template.render(
                            otlp_export_endpoint=otlp_export_endpoint,
                            prometheus_export_endpoint=f'{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_IP","0.0.0.0")}:{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_PORT","9999")}',
                            scrape_interval=self.agent.state.configuration.node_exporter_scrape_interval,
                            scrape_timeout=self.agent.state.configuration.node_exporter_scrape_interval,
                            mimir_export_endpoint=os.getenv("MLS_OTEL_MIMIR_EXPORT_ENDPOINT"),
                            loki_export_endpoint=os.getenv("MLS_OTEL_LOKI_EXPORT_ENDPOINT"),
                            tempo_export_endpoint=os.getenv("MLS_OTEL_TEMPO_EXPORT_ENDPOINT")
                        )

                        await create_svc(name_prefix="cluster-")
                        pod_name, config_name = await create_otel_pod(self.agent.state.hostname,parsed_otel_config)
                        self.otel_pod_list.append({
                            "node": self.agent.state.hostname,
                            "payload": parsed_otel_config,
                            "pod": pod_name,
                            "config": config_name}
                        )
                    if self.agent_state.configuration.node_exporter_enabled:
                        node_exporter_pod_port = int(os.getenv("MLS_NODE_EXPORTER_PORT", "9200"))
                        node_exporter_flags = os.getenv("MLS_OTEL_NODE_EXPORTER_FLAGS", "os")
                        pod_name = await deploy_node_exporter_pod(self.agent.state.hostname,node_exporter_flags,node_exporter_pod_port)
                        self.node_exporter_pod_list.append({
                            "node": self.agent.state.hostname,
                            "pod": pod_name,
                        })
                    return
                case "node":
                    if self.agent_state.configuration.otel_deploy_enabled:
                        # Render the template with the `otlp_export_endpoint`
                        otlp_export_endpoint_enabled = os.getenv("MLS_OTEL_HIGHER_EXPORT", "ON")
                        if otlp_export_endpoint_enabled == "ON":
                            otlp_export_endpoint = f'cluster-otel-collector.mls-telemetry.svc.cluster.local:{os.getenv("MLS_OTEL_CLUSTER_PORT","43170")}'
                        else:
                            otlp_export_endpoint = None
                        parsed_otel_config = template.render(
                            otlp_export_endpoint=otlp_export_endpoint,
                            prometheus_export_endpoint=f'{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_IP","0.0.0.0")}:{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_PORT","9999")}',
                            scrape_interval=self.agent.state.configuration.node_exporter_scrape_interval,
                            scrape_timeout=self.agent.state.configuration.node_exporter_scrape_interval,
                            mimir_export_endpoint=os.getenv("MLS_OTEL_MIMIR_EXPORT_ENDPOINT"),
                            loki_export_endpoint=os.getenv("MLS_OTEL_LOKI_EXPORT_ENDPOINT"),
                            tempo_export_endpoint=os.getenv("MLS_OTEL_TEMPO_EXPORT_ENDPOINT")
                        )
                        # Send the parsed content to the cluster
                        payload = {"node": self.agent.state.hostname, "otel_config": parsed_otel_config}
                        await self.agent.send_message_to_node(self.agent_state.configuration.cluster,mlsysops.events.MessageEvents.OTEL_DEPLOY.value,payload)

                    if self.agent_state.configuration.node_exporter_enabled:
                        node_exporter_pod_port = int(os.getenv("MLS_NODE_EXPORTER_PORT", "9200"))
                        node_exporter_flags = os.getenv("MLS_OTEL_NODE_EXPORTER_FLAGS", "os")
                        payload = {"node": self.agent.state.hostname, "port": node_exporter_pod_port, "flags": node_exporter_flags}
                        await self.agent.send_message_to_node(self.agent_state.configuration.cluster,mlsysops.events.MessageEvents.NODE_EXPORTER_DEPLOY.value,payload)
                    return
                case "continuum":
                    if self.agent_state.configuration.otel_deploy_enabled:
                        logger.debug("Applying continuum default telemetry configuration.")
                        # Render the template with the `otlp_export_endpoint`
                        otlp_export_endpoint = f'{os.getenv("MLS_OTEL_CONTINUUM_EXPORT_IP","None")}:{os.getenv("MLS_OTEL_CONTINUUM_EXPORT_PORT","43170")}'
                        if "None" in otlp_export_endpoint:
                            otlp_export_endpoint = None
                        parsed_otel_config = template.render(
                            otlp_export_endpoint=otlp_export_endpoint,
                            prometheus_export_endpoint="0.0.0.0:9999",
                            scrape_interval=self.agent.state.configuration.node_exporter_scrape_interval,
                            scrape_timeout=self.agent.state.configuration.node_exporter_scrape_interval,
                            mimir_export_endpoint=os.getenv("MLS_OTEL_MIMIR_EXPORT_ENDPOINT"),
                            loki_export_endpoint=os.getenv("MLS_OTEL_LOKI_EXPORT_ENDPOINT"),
                            tempo_export_endpoint=os.getenv("MLS_OTEL_TEMPO_EXPORT_ENDPOINT")
                        )

                        await create_svc()
                        pod_name, config_name = await create_otel_pod(self.agent.state.hostname, parsed_otel_config)
                        self.node_exporter_pod_list.append({
                            "node": self.agent.state.hostname,
                            "pod": pod_name,
                        })
                    if self.agent_state.configuration.node_exporter_enabled:
                        node_exporter_pod_port = int(os.getenv("MLS_NODE_EXPORTER_PORT", "9200"))
                        node_exporter_flags = os.getenv("MLS_OTEL_NODE_EXPORTER_FLAGS", "os")
                        pod_name = await deploy_node_exporter_pod(self.agent.state.hostname, node_exporter_flags,
                                                                  node_exporter_pod_port)
                        self.node_exporter_pod_list.append({
                            "node": self.agent.state.hostname,
                            "pod": pod_name,
                        })
                    return
        except Exception as e:
            logger.error(f"An error occurred while reading the configuration file: {e}")
            logger.error(traceback.format_exc())

    async def remote_apply_otel_configuration(self, node_name, otel_payload):
        """
        Applies OpenTelemetry (OTEL) configuration to a specified node by creating an OTEL pod
        with the given configuration payload. Logs errors if the operation fails.
        It is received from remote agents.

        Arguments:
            node_name (str): The name of the node where the OTEL configuration will be applied.
            otel_payload (dict): The OTEL configuration details.

        Raises:
            Exception: If an error occurs during the creation of the OTEL pod.
        """
        try:
            logger.debug(f"Applying OTEL configuration for node {node_name}")
            pod_name,config_name = await create_otel_pod(node_name,otel_payload)
            self.otel_pod_list.append({
                "node":node_name,
                "payload": otel_payload,
                "pod": pod_name,
                "config": config_name}
            )
        except Exception as e:
            logger.error(f"An error occurred while applying the OTEL configuration for node {node_name}: {e}")

    async def remote_remove_pod(self, node_name):
        """
        Remove an OTEL pod from a specific node and update the internal pod list.

        This asynchronous method attempts to delete the OTEL pod corresponding to the
        given node name and removes it from the `otel_pod_list`. If the pod cannot
        be removed or another error occurs during the process, an error message is
        logged.

        Parameters:
            node_name: str
                The name of the node for which the OTEL pod should be removed.

        Raises:
            Exception
                If any error occurs during the removal of the OTEL pod.
        """
        try:
            logger.debug(f"Remove OTEL pod for node {node_name}")
            delete_otel_pod(node_name)
            for otel_pod in self.otel_pod_list:
                if otel_pod["node"] == node_name:
                    self.otel_pod_list.remove(otel_pod)
                    break
        except Exception as e:
            logger.error(f"An error occurred while removing OTEL pod for {node_name}: {e}")

    async def remote_apply_node_exporter(self,payload):
        """
        Handles the deployment of a node exporter pod on a specified node in an
        asynchronous manner. The function logs the process, applies the
        configuration, and tracks the pod details in the `otel_pod_list`.

        Args:
            payload (dict):
                A dictionary containing parameters for the node exporter application. Expected keys
                include:
                - 'node': str, the node name where the pod will be deployed.
                - 'flags': list, optional flags for configuring the node exporter pod.
                - 'port': int, the port number to use for the deployment.

        Raises:
            Exception:
                If any error occurs during the node exporter's deployment or pod
                configuration, an exception is raised and logged, interrupting the
                operation.
        """
        try:
            logger.debug(f"Applying node exporter message node {payload['node']}")
            pod_name = await deploy_node_exporter_pod(
                node_name=payload['node'],
                flags=payload['flags'],
                port=payload['port'])

            self.node_exporter_pod_list.append({
                "node":payload['node'],
                "payload": payload,
                "pod": pod_name
            }
            )
        except Exception as e:
            logger.error(f"An error occurred while applying the node exporter for node {payload['node']}: {e}")

    async def remote_remove_node_exporter_pod(self, node_name):

        try:
            logger.debug(f"Remove node exporter node pod for node {node_name}")
            delete_node_exporter_pod(node_name)
            for node_exporter_pod in self.node_exporter_pod_list:
                if node_exporter_pod["node"] == node_name:
                    self.node_exporter_pod_list.remove(node_exporter_pod)
                    break
        except Exception as e:
            logger.error(f"An error occurred while removing node exporter pod for {node_name}: {e}")




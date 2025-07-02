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
import re
import traceback
import asyncio
import mlsysops.events
from jinja2 import Template, PackageLoader, Environment, select_autoescape
from mlsysops.controllers.base import BaseController
from mlsysops.logger_util import logger
from .libs import create_otel_pod_with_restart
from .libs.otel_pods import create_otel_pod, create_svc, delete_otel_pod, remove_service, deploy_node_exporter_pod, \
    delete_node_exporter_pod

class TelemetryController(BaseController):

    def __init__(self, agent):
        logger.debug("Initializing telemetry controller...")
        self.agent = agent
        self.otel_pod_list = []
        self.node_exporter_pod_list = []
        self.local_config = None
        self.requests_scrape_intervals = {"default": parse_interval_string(agent.state.configuration.node_exporter_scrape_interval)}
        self.node_scrape_intervals = {"default": parse_interval_string(agent.state.configuration.node_exporter_scrape_interval)}
        self.current_scrape_interval = self.node_scrape_intervals['default']

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
                    asyncio.create_task(self.agent.send_message_to_node(self.agent.state.configuration.cluster,mlsysops.events.MessageEvents.OTEL_REMOVE.value,payload))
            case "continuum":
                delete_otel_pod(self.agent.state.hostname)
                remove_service()
                pass

    def get_current_scrape_interval(self):
        return self.current_scrape_interval

    async def apply_configuration_telemetry(self):
        # add metrics from the configuration file
        if (self.agent.state.configuration is not None
                and
                self.agent.state.configuration.default_telemetry_metrics != "None"):
            # enable system metrics with current config for monitor tasks
            for metric_name in self.agent.state.configuration.default_telemetry_metrics:
                logger.debug(f"Adding metric {metric_name} to monitor task.")
                await self.agent.monitor_task.add_metric(metric_name)

    def get_telemetry_configuration(self, **args):
        parsed_otel_config = None

        # Define the loader for Jinja environment
        loader = PackageLoader("mlsysops", "templates")
        env = Environment(
            loader=loader,
            autoescape=select_autoescape(enabled_extensions=("j2"))
        )

        # Load the template
        template = env.get_template("otel-config.yaml.j2")

        try:
            parsed_otel_config = template.render(args)

        except Exception as e:
            logger.error(f"An error occurred while reading the configuration file: {e}")
            logger.error(traceback.format_exc())

        return parsed_otel_config

    def create_otel_deployment(self, interval):
        pass

    async def initialize(self):
        """
        Reads the otel-config.yaml file, parses its content, and sends it to the cluster.
        """
        try:
            # Log the parsed content (for debugging purposes)
            logger.debug(f"Parsed OTEL configuration for level {self.agent.state.configuration.continuum_layer}")

            scrape_interval = parse_interval_string(
                self.agent.state.configuration.node_exporter_scrape_interval)

            self.current_scrape_interval = scrape_interval
            self.requests_scrape_intervals['default'] = scrape_interval

            match self.agent.state.configuration.continuum_layer:
                case "none":
                    logger.debug("No target level configuration applied.")
                    return
                case "cluster":
                    logger.debug("Applying cluster default telemetry configuration.")
                    if self.agent.state.configuration.otel_deploy_enabled:
                        # Render the template with the `otlp_export_endpoint`
                        otlp_export_endpoint_enabled = os.getenv("MLS_OTEL_HIGHER_EXPORT", "ON")
                        if otlp_export_endpoint_enabled == "ON":
                            otlp_export_endpoint = f'{os.getenv("EJABBERD_DOMAIN","127.0.0.1")}:{os.getenv("MLS_OTEL_CONTINUUM_PORT","43170")}'
                        else:
                            otlp_export_endpoint = None

                        parsed_otel_config = self.get_telemetry_configuration(
                            otlp_export_endpoint=otlp_export_endpoint,
                            prometheus_export_endpoint=f'{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_IP","0.0.0.0")}:{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_PORT","9999")}',
                            scrape_interval=self.agent.state.configuration.node_exporter_scrape_interval,
                            scrape_timeout=self.agent.state.configuration.node_exporter_scrape_interval,
                            mimir_export_endpoint=os.getenv("MLS_OTEL_MIMIR_EXPORT_ENDPOINT"),
                            loki_export_endpoint=os.getenv("MLS_OTEL_LOKI_EXPORT_ENDPOINT"),
                            tempo_export_endpoint=os.getenv("MLS_OTEL_TEMPO_EXPORT_ENDPOINT"),
                            k8s_cluster_receiver=None,
                            local_endpoint_metrics_expiration=str(scrape_interval + 5) + "s",
                        )

                        self.local_config = parsed_otel_config

                        await create_svc(name_prefix="cluster-")
                        pod_name, config_name = await create_otel_pod(self.agent.state.hostname,parsed_otel_config)
                        self.otel_pod_list.append({
                            "node": self.agent.state.hostname,
                            "payload": parsed_otel_config,
                            "pod": pod_name,
                            "config": config_name}
                        )
                    if self.agent.state.configuration.node_exporter_enabled:
                        node_exporter_pod_port = int(os.getenv("MLS_NODE_EXPORTER_PORT", "9200"))
                        node_exporter_flags = os.getenv("MLS_OTEL_NODE_EXPORTER_FLAGS", "os")
                        pod_name = await deploy_node_exporter_pod(self.agent.state.hostname,node_exporter_flags,node_exporter_pod_port)
                        self.node_exporter_pod_list.append({
                            "node": self.agent.state.hostname,
                            "pod": pod_name,
                        })
                    return
                case "node":
                    if self.agent.state.configuration.otel_deploy_enabled:
                        # Render the template with the `otlp_export_endpoint`
                        otlp_export_endpoint_enabled = os.getenv("MLS_OTEL_HIGHER_EXPORT", "ON")
                        if otlp_export_endpoint_enabled == "ON":
                            otlp_export_endpoint = f'cluster-otel-collector.mlsysops-framework.svc.cluster.local:{os.getenv("MLS_OTEL_CLUSTER_PORT","43170")}'
                        else:
                            otlp_export_endpoint = None
                        parsed_otel_config = self.get_telemetry_configuration(
                            otlp_export_endpoint=otlp_export_endpoint,
                            prometheus_export_endpoint=f'{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_IP","0.0.0.0")}:{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_PORT","9999")}',
                            scrape_interval=self.agent.state.configuration.node_exporter_scrape_interval,
                            scrape_timeout=self.agent.state.configuration.node_exporter_scrape_interval,
                            mimir_export_endpoint=os.getenv("MLS_OTEL_MIMIR_EXPORT_ENDPOINT"),
                            loki_export_endpoint=os.getenv("MLS_OTEL_LOKI_EXPORT_ENDPOINT"),
                            tempo_export_endpoint=os.getenv("MLS_OTEL_TEMPO_EXPORT_ENDPOINT"),
                            k8s_cluster_receiver=None,
                            local_endpoint_metrics_expiration=str(scrape_interval + 5) + "s",

                        )

                        self.local_config = parsed_otel_config

                        # Send the parsed content to the cluster
                        payload = {"node": self.agent.state.hostname, "otel_config": parsed_otel_config, "interval": scrape_interval}
                        await self.agent.send_message_to_node(self.agent.state.configuration.cluster,mlsysops.events.MessageEvents.OTEL_DEPLOY.value,payload)

                    if self.agent.state.configuration.node_exporter_enabled:
                        node_exporter_pod_port = int(os.getenv("MLS_NODE_EXPORTER_PORT", "9200"))
                        node_exporter_flags = os.getenv("MLS_OTEL_NODE_EXPORTER_FLAGS", "os")
                        payload = {"node": self.agent.state.hostname, "port": node_exporter_pod_port, "flags": node_exporter_flags}
                        await self.agent.send_message_to_node(self.agent.state.configuration.cluster,mlsysops.events.MessageEvents.NODE_EXPORTER_DEPLOY.value,payload)
                    return
                case "continuum":
                    if self.agent.state.configuration.otel_deploy_enabled:
                        logger.debug("Applying continuum default telemetry configuration.")
                        # Render the template with the `otlp_export_endpoint`
                        otlp_export_endpoint = f'{os.getenv("MLS_OTEL_CONTINUUM_EXPORT_IP","None")}:{os.getenv("MLS_OTEL_CONTINUUM_EXPORT_PORT","43170")}'
                        if "None" in otlp_export_endpoint:
                            otlp_export_endpoint = None
                        parsed_otel_config = self.get_telemetry_configuration(
                            otlp_export_endpoint=otlp_export_endpoint,
                            prometheus_export_endpoint="0.0.0.0:9999",
                            scrape_interval=self.agent.state.configuration.node_exporter_scrape_interval,
                            scrape_timeout=self.agent.state.configuration.node_exporter_scrape_interval,
                            mimir_export_endpoint=os.getenv("MLS_OTEL_MIMIR_EXPORT_ENDPOINT"),
                            loki_export_endpoint=os.getenv("MLS_OTEL_LOKI_EXPORT_ENDPOINT"),
                            tempo_export_endpoint=os.getenv("MLS_OTEL_TEMPO_EXPORT_ENDPOINT"),
                            local_endpoint_metrics_expiration=str(scrape_interval + 5) + "s",
                        )

                        self.local_config = parsed_otel_config

                        await create_svc()
                        pod_name, config_name = await create_otel_pod(self.agent.state.hostname, parsed_otel_config)
                        self.node_exporter_pod_list.append({
                            "node": self.agent.state.hostname,
                            "pod": pod_name,
                        })
                    if self.agent.state.configuration.node_exporter_enabled:
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

    async def remote_apply_otel_configuration(self, node_name, otel_payload, interval=None):
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
            pod_name,config_name = await create_otel_pod_with_restart(node_name,otel_payload)
            self.otel_pod_list.append({
                "node":node_name,
                "payload": otel_payload,
                "pod": pod_name,
                "config": config_name}
            )
            if interval is not None:
                self.node_scrape_intervals[node_name] = interval
                # if node has out-of-sync configuration, inform it
                logger.debug(f"Node {node_name} has out-of-sync configuration, informing it {interval} - {self.current_scrape_interval}")
                if interval != self.current_scrape_interval:
                    payload = {"node": node_name, "interval": self.current_scrape_interval},
                    await self.agent.send_message_to_node(node_name,
                                                          mlsysops.events.MessageEvents.OTEL_NODE_INTERVAL_UPDATE.value,
                                                          payload)
        except Exception as e:
            logger.error(f"An error occurred while applying the OTEL configuration for node {node_name}: {traceback.format_exc()}")

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
            delete_node_exporter_pod(node_name)
            for node_exporter_pod in self.node_exporter_pod_list:
                if node_exporter_pod["node"] == node_name:
                    self.node_exporter_pod_list.remove(node_exporter_pod)
                    break
        except Exception as e:
            logger.error(f"An error occurred while removing node exporter pod for {node_name}: {e}")

    async def add_new_interval(self, id, new_interval):
        try:
            if type(new_interval) is not int:
                self.requests_scrape_intervals[id] = parse_interval_string(new_interval)
            else:
                self.requests_scrape_intervals[id] = new_interval

            new_min_interval_key = min(self.requests_scrape_intervals, key=self.requests_scrape_intervals.get)
            new_min_interval = self.requests_scrape_intervals[new_min_interval_key]

            if self.current_scrape_interval != new_min_interval:
                self.current_scrape_interval = new_min_interval
                await self.apply_interval_change()
        except Exception as e:
            logger.error(f"An error occurred while adding new interval: {traceback.format_exc()}")

    async def remove_interval(self, id):
        del self.requests_scrape_intervals[id]
        new_min_interval = min(self.requests_scrape_intervals, key=self.requests_scrape_intervals.get)
        if self.current_scrape_interval != new_min_interval:
            await self.apply_interval_change()

    async def apply_interval_change(self):
        """
        This asynchronous function applies interval changes to the monitoring tasks
        based on the current configuration context, which could be "node", "cluster",
        or "continuum". It appropriately configures monitoring intervals, communicates
        with cluster nodes, or delegates responsibilities depending on the defined
        context.

        Raises:
            TypeError: If the data sent to `send_message_to_node` does not match
                       the expected payload format.

        Parameters:
            self: This is the instance of the class to which this method belongs.
        """
        # Configure the monitor task scrape interval for current level
        await self.agent.monitor_task.set_monitor_interval(self.get_current_scrape_interval())

        match self.agent.state.configuration.continuum_layer:
            case "node":
                # if we are in node, then just ask the higher agent to make the change.
                await self.apply_node_interval_change()
            case "cluster":
                # change the cluster otel collector
                await self.apply_cluster_interval_change()

                # Request from node otel collectors to change
                for otel_pod in self.otel_pod_list:
                    if otel_pod["node"] == self.agent.state.hostname:
                        # skip local
                        continue

                    payload = {"node": otel_pod['node'], "interval": self.current_scrape_interval},
                    await self.agent.send_message_to_node(otel_pod['node'],
                                                          mlsysops.events.MessageEvents.OTEL_NODE_INTERVAL_UPDATE.value, payload)
            case "continuum":
                return

    async def apply_cluster_interval_change(self):
        if self.agent.state.configuration.otel_deploy_enabled:
            # Render the template with the `otlp_export_endpoint`
            otlp_export_endpoint_enabled = os.getenv("MLS_OTEL_HIGHER_EXPORT", "ON")
            if otlp_export_endpoint_enabled == "ON":
                otlp_export_endpoint = f'{os.getenv("EJABBERD_DOMAIN", "127.0.0.1")}:{os.getenv("MLS_OTEL_CONTINUUM_PORT", "43170")}'
            else:
                otlp_export_endpoint = None

            parsed_otel_config = self.get_telemetry_configuration(
                otlp_export_endpoint=otlp_export_endpoint,
                prometheus_export_endpoint=f'{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_IP", "0.0.0.0")}:{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_PORT", "9999")}',
                scrape_interval=str(self.get_current_scrape_interval()) + "s",
                scrape_timeout=str(self.get_current_scrape_interval()) + "s",
                mimir_export_endpoint=os.getenv("MLS_OTEL_MIMIR_EXPORT_ENDPOINT"),
                loki_export_endpoint=os.getenv("MLS_OTEL_LOKI_EXPORT_ENDPOINT"),
                tempo_export_endpoint=os.getenv("MLS_OTEL_TEMPO_EXPORT_ENDPOINT"),
                k8s_cluster_receiver=None,
                local_endpoint_metrics_expiration=str(self.get_current_scrape_interval() + 5) + "s",
            )

            self.local_config = parsed_otel_config

            try:
                await create_svc(name_prefix="cluster-")
                await create_otel_pod_with_restart(self.agent.state.hostname, parsed_otel_config)
                ## todo update local dict
            except Exception as e:
                logger.error(f"An error occurred while applying the OTEL configuration for node {traceback.format_exc()}: {e}")


    async def apply_node_interval_change(self):
        """
        Apply a new scraping interval for telemetry configuration and send the appropriate
        updated configuration to the cluster. This function handles both OpenTelemetry
        and node exporter configurations if enabled.

        It records the minimum scraping interval that were requested (from different policies) and applies it.

        Args:
            id: The id of the entity that requested the change. (policy, mechanism etc).
            new_interval (int): The new scrape interval to apply for telemetry configurations.

        Raises:
            None
        """
        min_requested_interval = self.get_current_scrape_interval()

        if (self.agent.state.configuration.otel_deploy_enabled and
                self.agent.state.configuration.continuum_layer == "node"): # enabled only for nodes

            # Render the template with the `otlp_export_endpoint`
            otlp_export_endpoint_enabled = os.getenv("MLS_OTEL_HIGHER_EXPORT", "ON")
            if otlp_export_endpoint_enabled == "ON":
                otlp_export_endpoint = f'cluster-otel-collector.mlsysops-framework.svc.cluster.local:{os.getenv("MLS_OTEL_CLUSTER_PORT", "43170")}'
            else:
                otlp_export_endpoint = None
            parsed_otel_config = self.get_telemetry_configuration(
                otlp_export_endpoint=otlp_export_endpoint,
                prometheus_export_endpoint=f'{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_IP", "0.0.0.0")}:{os.getenv("MLS_OTEL_PROMETHEUS_LISTEN_PORT", "9999")}',
                scrape_interval=str(min_requested_interval) + "s",
                scrape_timeout=str(min_requested_interval) + "s",
                mimir_export_endpoint=os.getenv("MLS_OTEL_MIMIR_EXPORT_ENDPOINT"),
                loki_export_endpoint=os.getenv("MLS_OTEL_LOKI_EXPORT_ENDPOINT"),
                tempo_export_endpoint=os.getenv("MLS_OTEL_TEMPO_EXPORT_ENDPOINT"),
                k8s_cluster_receiver=None,
                local_endpoint_metrics_expiration=str(min_requested_interval + 5) + "s",

            )


            self.local_config = parsed_otel_config

            # Send the parsed content to the cluster
            payload = {"node": self.agent.state.hostname, "otel_config": parsed_otel_config, "interval": min_requested_interval}
            await self.agent.send_message_to_node(self.agent.state.configuration.cluster,
                                                  mlsysops.events.MessageEvents.OTEL_DEPLOY.value, payload)
            logger.debug(f"Sent telemetry configuration to cluster for node {min_requested_interval}")

## Utility methods
def parse_interval_string(interval_string):
    """
       Parses an analyze interval string in the format 'Xs|Xm|Xh|Xd' and converts it to seconds.

       Args:
           interval_string (str): The analyze interval as a string (e.g., "5m", "2h", "1d").

       Returns:
           int: The interval in seconds.

       Raises:
           ValueError: If the format of the interval string is invalid.
       """
    # Match the string using a regex: an integer followed by one of s/m/h/d
    match = re.fullmatch(r"(\d+)([smhd])", interval_string)
    if not match:
        logger.error(f"Invalid analyze interval format: '{interval_string}'")
        return 0

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
        raise ValueError(f"Unsupported time unit '{unit}' in interval: '{interval_string}'")

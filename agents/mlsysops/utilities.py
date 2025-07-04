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

from .logger_util import logger
import operator

def evaluate_condition(a, b, operator: str) -> bool:
    """
    Evaluates a condition based on the given operator.

    Args:
        a (Any): Left operand.
        b (Any): Right operand.
        operator (str): The operator as a string. Valid values are:
            - "lower_or_equal" (<=)
            - "greater_or_equal" (>=)
            - "equal" (==)
            - "lower_than" (<)
            - "greater_than" (>)

    Returns:
        bool: The result of the condition.

    Raises:
        ValueError: If the operator is not valid.
    """
    if operator == "lower_or_equal":
        return a <= b
    elif operator == "greater_or_equal":
        return a >= b
    elif operator == "equal":
        return a == b
    elif operator == "lower_than":
        return a < b
    elif operator == "greater_than":
        return a > b
    else:
        raise ValueError(f"Invalid operator: {operator}")

def cmp_fields(comp_field, node_field, op, resource):
    if comp_field and (not node_field or op(comp_field, node_field)):
        logger.error(f"{resource}: Node field {node_field} does not match comp requirement: {comp_field}")
        return False
    return True

def node_matches_requirements(node, comp_spec):
    """Check if node matches description-related requirements.

    Args:
        node (dict): The MLSysOpsNode description.
        comp_spec (dict): A component's extended spec.

    Returns:
        bool: True, if the node matches the requirements, False otherwise
    """
    logger.info(f"Checking requirements for node: {node['metadata']['name']}")
    node_name = node.get("metadata").get("name")
    placement = comp_spec.get("node_placement", None)

    if placement:
        host = placement.get("node", None)

        if host and host != node_name:
            logger.error(f"Selected host {node_name} does not match description-related host {host}")
            return False

        node_layer = placement.get("continuum_layer", None)
        if node_layer and "*" not in node_layer:
            if 'continuum_layer' not in node:
                logger.error(f"Node {node_name} does not have continuum_layer")
                return False
            match_layer = False
            for layer in node_layer:
                if layer == node['continuum_layer']:
                    match_layer = True
                    break

            if not match_layer:
                logger.error(f"Node {node} does not match node layer")
                return False

        mobility = placement.get("mobile", False)
        if mobility and not node.get("mobile", False):
            logger.error(f"Node {node_name} is not mobile")
            return False

        comp_labels = placement.get("labels", None)
        # logger.info(f"comp_labels {comp_labels}")

        node_labels = node.get("labels", None)
        # logger.info(f"node_labels {node_labels}")

        if comp_labels:

            if not node_labels:
                logger.error(f"Node {node_name} does not match comp labels {comp_labels}")
                return False

            for label in comp_labels:
                if label not in node_labels:
                    logger.error(f"Node {node_name} does not match comp label {label}")
                    return False

    sensors = comp_spec.get("sensors", None)
    if sensors:
        for sensor in sensors:
            camera = sensor.get("camera", None)
            if camera:
                node_camera = None
                for node_sensor in node['sensors']:
                    if 'camera' in node_sensor:
                        node_camera = node_sensor['camera']
                        break

                if not node_camera:
                    logger.error(f"Node does not have camera sensor")
                    return False

                if not cmp_fields(camera.get("model", None), node_camera.get("model", None), operator.ne,
                                  "camera model"):
                    return False

                if not cmp_fields(camera.get("camera_type", None), node_camera.get("camera_type", None), operator.ne,
                                  "camera type"):
                    return False

                if not cmp_fields(camera.get("minimum_framerate", None), node_camera.get("framerate", None),
                                  operator.gt, "camera framerate"):
                    return False

                resolution = camera.get("resolution", None)
                node_resolutions = node_camera.get("supported_resolutions", [])
                if resolution and resolution not in node_resolutions:
                    logger.error(f"Node does not match camera resolution requirements")
                    return False

            temperature = sensor.get("temperature", None)
            if temperature:
                node_temperature = None
                for node_sensor in node['sensors']:
                    if 'temperature' in node_sensor:
                        node_temperature = node_sensor['temperature']
                        break

                if not node_temperature:
                    logger.error(f"Node does not have temperature sensor")
                    return False

                if not cmp_fields(temperature.get("model", None), node_temperature.get("model", None), operator.ne,
                                  "temperature model"):
                    return False
    node_env = node.get("environment", None)
    if not cmp_fields(comp_spec.get("node_type", None), node_env.get("node_type", None), operator.ne, "node type"):
        return False

    if not cmp_fields(comp_spec.get("os", None), node_env.get("os", None), operator.ne, "os"):
        return False

    container_runtime = comp_spec.get("container_runtime", None)
    node_container_runtimes = node_env.get("container_runtime", [])
    if container_runtime and container_runtime not in node_container_runtimes:
        logger.error(f"Node does not match container runtime requirements")
        return False

    # NOTE: We assume single container components
    container = comp_spec.get("containers")[0]
    # logger.info(f"comp_spec {comp_spec}")
    platform_requirements = container.get("platform_requirements")
    if platform_requirements:
        cpu = platform_requirements.get("cpu", None)
        node_hw = node.get("hardware", None)
        if cpu:
            node_cpu = node_hw.get("cpu", None)
            cpu_arch_list = cpu.get("architecture", None)
            if cpu_arch_list and not node_cpu:
                logger.error(f"Node does not have cpu arch info")
                return False

            node_cpu_arch = node_cpu.get("architecture", None)
            if (cpu_arch_list and not node_cpu_arch) or (node_cpu_arch and node_cpu_arch not in cpu_arch_list):
                logger.error(
                    f"Node {node_cpu_arch} does not have any of the required cpu architectures {cpu_arch_list}")
                return False

            cpu_freq = cpu.get("frequency", None)
            if cpu_freq and not node_cpu:
                logger.error(f"Node does not have cpu freq info")
                return False

            node_cpu_freq = node_cpu.get("frequency", [])
            if cpu_freq:
                found = False
                for freq in node_cpu_freq:
                    if cpu_freq <= freq:
                        found = True
                        break

                if not found:
                    logger.error(f"Node does not have cpu freq equal to or greater than the requested")
                    return False

            cpu_perf = cpu.get("performance_indicator", None)
            if cpu_perf and not node_cpu:
                logger.error(f"Node does not have cpu perf info")
                return False

            if not cmp_fields(cpu_perf, node_cpu.get("performance_indicator", None), operator.gt, "cpu perf indicator"):
                return False

        if not cmp_fields(platform_requirements.get("disk", None), node_hw.get("disk", None), operator.gt, "disk"):
            return False

        gpu = platform_requirements.get("gpu", None)
        if gpu:
            node_gpu = node_hw.get("gpu", None)
            gpu_model = gpu.get("model", None)
            if gpu_model and not node_gpu:
                logger.error(f"Node does not have gpu info")
                return False

            if not cmp_fields(gpu_model, node_gpu.get("model", None), operator.ne, "gpu model"):
                return False

            gpu_mem = gpu.get("memory", None)
            if gpu_mem and not node_gpu:
                logger.error(f"Node does not have gpu info")
                return False

            if not cmp_fields(gpu_mem, node_gpu.get("memory", None), operator.gt, "gpu memory"):
                return False

            gpu_perf = gpu.get("performance_indicator", None)
            if gpu_perf and not node_gpu:
                logger.error(f"Node does not have gpu info")
                return False

            if not cmp_fields(gpu_perf, node_gpu.get("performance_indicator", None), operator.gt, "gpu perf indicator"):
                return False

    return True
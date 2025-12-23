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

import socket
from dataclasses import dataclass, field
from typing import List, Dict
import yaml
import os

def _get_mechanisms_list():
    """
    Get mechanisms list from MLS_MECHANISM_ENABLED environment variable.
    
    Returns:
        List[str]: List of mechanisms from comma-separated env variable, or empty list if not set.
    """
    env_value = os.getenv("MLS_MECHANISM_ENABLED")
    if env_value is None:
        return []
    return [m.strip() for m in env_value.split(",") if m.strip()]


def _get_bool_env(env_var: str, default: bool):
    """
    Get boolean value from environment variable.
    
    Args:
        env_var: Environment variable name
        default: Default value if env variable not set
        
    Returns:
        bool: True if env var is 'true', '1', 'yes', 'on' (case-insensitive), False otherwise
    """
    env_value = os.getenv(env_var)
    if env_value is None:
        return default
    return env_value.lower() in ('true', '1', 'yes', 'on')


@dataclass
class AgentConfig:
    """
    Dataclass representing the agent configuration.
    """
    mechanisms: List[str] = field(default_factory=lambda: _get_mechanisms_list())
    default_telemetry_metrics: List[str] = field(default_factory=list)
    policy_directory: str = field(default_factory=lambda: os.getenv("MLS_POLICY_DIRECTORY", "/etc/mlsysops/policies"))
    mechanisms_directory: str = field(default_factory=lambda: os.getenv("MLS_MECHANISMS_DIRECTORY", "/etc/mlsysops/mechanisms"))
    continuum_layer: str = ""
    behaviours: Dict[str, bool] = field(default_factory=dict)

    system_description: dict = field(default_factory=dict)

    # Telemetry
    node_exporter_scrape_interval: str = field(default_factory=lambda: os.getenv("MLS_NODE_EXPORTER_SCRAPE_INTERVAL", "5s"))
    monitoring_interval: str = field(default_factory=lambda: os.getenv("MLS_MONITORING_INTERVAL", "5s"))

    node_exporter_enabled: bool = field(default_factory=lambda: _get_bool_env("MLS_NODE_EXPORTER_ENABLED", True))
    otel_deploy_enabled: bool = field(default_factory=lambda: _get_bool_env("MLS_OTEL_DEPLOY_ENABLED", True))
    node_exporter_collectors: str = field(default_factory=lambda: os.getenv("MLS_NODE_EXPORTER_METRICS", "os"))
    enable_core_policies: bool = field(default_factory=lambda: _get_bool_env("MLS_CORE_POLICIES_ENABLED", True))

    node: str = field(default_factory=lambda: os.getenv("NODE_NAME", socket.gethostname()))
    cluster: str = field(default_factory=lambda: os.getenv("CLUSTER_NAME", ""))
    domain: str = field(default_factory=lambda: os.getenv("EJABBERD_DOMAIN", ""))
    n_pass: str = field(default_factory=lambda: os.getenv("NODE_PASSWORD", ""))
    n_jid: str = field(init=False)
    c_jid: str = field(init=False)

    # Watchdog / TTL configuration (can be overridden by configuration or policy context)
    task_ttl: float = field(
        default_factory=lambda: float(os.getenv("MLS_TASK_TTL_SECONDS", "60.0"))
    )
    watchdog_interval: float = field(
        default_factory=lambda: float(os.getenv("MLS_WATCHDOG_INTERVAL_SECONDS", "1.0"))
    )

    def __post_init__(self):
        """
        Calculate derived fields after initialization, e.g., JIDs.
        """
        self.n_jid = f"{self.node}@{self.domain}" if self.node and self.domain else ""
        self.c_jid = f"{self.cluster}@{self.domain}" if self.cluster and self.domain else ""

    def update(self, **kwargs):
        """
        Updates the attributes of an object based on provided keyword arguments.
        Certain attributes are protected from updates if their respective environment
        variables are set. If keys related to derived fields are modified,
        recalculation is triggered.

        Parameters:
            **kwargs: dict
                Keyword arguments containing keys and corresponding values to
                update the attributes of the object.

        Raises:
            KeyError
                If an invalid configuration key is provided that does not match
                any existing attribute of the object.
        """
        # Keys that should not be updated if their corresponding env variable is set
        env_protected_keys = {
            "enable_core_policies": "MLS_CORE_POLICIES",
            "policy_directory": "MLS_POLICY_DIRECTORY",
            "mechanisms_directory": "MLS_MECHANISM_DIRECTORY",
            "mechanisms": "MLS_MECHANISM_ENABLED",
            "node_exporter_enabled": "MLS_NODE_EXPORTER_ENABLED",
            "otel_deploy_enabled": "MLS_OTEL_DEPLOY_ENABLED",
            "node_exporter_collectors": "MLS_NODE_EXPORTER_METRICS",
            "monitoring_interval": "MLS_MONITORING_INTERVAL",
            "node_exporter_scrape_interval": "MLS_NODE_EXPORTER_SCRAPE_INTERVAL"
        }
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                # Skip update if this key has an env variable set
                if key in env_protected_keys and os.getenv(env_protected_keys[key]) is not None:
                    continue
                    
                setattr(self, key, value)
                # Recalculate derived fields if needed
                if key in {"node", "cluster", "domain"}:
                    self.__post_init__()
            else:
                raise KeyError(f"Invalid configuration key: {key}")
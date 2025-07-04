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


@dataclass
class AgentConfig:
    """
    Dataclass representing the agent configuration.
    """
    mechanisms: List[str] = field(default_factory=list)
    default_telemetry_metrics: List[str] = field(default_factory=list)
    policy_directory: str = ""
    mechanisms_directory: str = ""
    continuum_layer: str = ""
    behaviours: Dict[str, bool] = field(default_factory=dict)

    system_description: dict = field(default_factory=dict)

    # Telemetry
    node_exporter_scrape_interval: str = "5s"
    monitoring_interval: str = "5s"

    node_exporter_enabled: bool = True
    otel_deploy_enabled: bool = True

    node: str = field(default_factory=lambda: os.getenv("NODE_NAME", socket.gethostname()))
    cluster: str = field(default_factory=lambda: os.getenv("CLUSTER_NAME", ""))
    domain: str = field(default_factory=lambda: os.getenv("EJABBERD_DOMAIN", ""))
    n_pass: str = field(default_factory=lambda: os.getenv("NODE_PASSWORD", ""))
    n_jid: str = field(init=False)
    c_jid: str = field(init=False)

    def __post_init__(self):
        """
        Calculate derived fields after initialization, e.g., JIDs.
        """
        self.n_jid = f"{self.node}@{self.domain}" if self.node and self.domain else ""
        self.c_jid = f"{self.cluster}@{self.domain}" if self.cluster and self.domain else ""

    def update(self, **kwargs):
        """
        Updates the configuration object with new values.
        :param kwargs: Key-value pairs to update the configuration.
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                # Recalculate derived fields if needed
                if key in {"node", "cluster", "domain"}:
                    self.__post_init__()
            else:
                raise KeyError(f"Invalid configuration key: {key}")
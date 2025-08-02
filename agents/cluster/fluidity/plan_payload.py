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

#/usr/bin/python3

from pydantic import BaseModel, Field, ValidationError, model_validator, RootModel
from typing import Any, Dict, List, Optional, Union
import re
from agents.mlsysops.logger_util import logger


class PlatformRequirements(BaseModel):
    cpu: Dict[str, Union[List[str], int, float, str]] = Field(..., description="CPU-related requirements like architecture, limits, frequency, etc.")
    disk: str = Field(..., description="Disk size in GB or appropriate units.")
    memory: Dict[str, str] = Field(..., description="Memory limits and requests.")
    performance_indicator: Optional[int] = Field(None, description="Performance indicator value.")


class ContainerConfig(BaseModel):
    image: str = Field(..., description="Container image in the format 'string1:string2'.")
    runtime_class_name: Optional[str] = Field(None, description="Runtime class name for the container.")
    platform_requirements: PlatformRequirements = Field(..., description="Platform-specific resource requirements.")
    other_fields: Dict[str, Any] = Field(default_factory=dict, description="Generic dictionary for other configuration options.")

    @model_validator(mode="after")
    def validate_image_format(self):
        # Ensure that the `image` field matches the `string1:string2` required format
        image_pattern = r"^[a-zA-Z0-9\-_.]+:[a-zA-Z0-9\-_.]+$"
        if not re.match(image_pattern, self.image):
            raise ValueError(f"Invalid image format: {self.image}. It must be in 'string1:string2' format.")
        return self


class DeploymentAction(BaseModel):
    action: str = Field(..., description="Type of action to perform (deploy, change_spec, move, etc.).")
    host: Optional[str] = Field(None, description="Host for the action (if applicable).")
    new_spec: Optional[ContainerConfig] = Field(None, description="New specification for 'change_spec' action.")

    @model_validator(mode="after")
    def validate_action(self):
        if self.action == "change_spec" and not self.new_spec:
            raise ValueError("'change_spec' action must include a valid 'new_spec' configuration.")
        return self



class DeploymentPlan(RootModel):
    root: Dict[str, Union[List[DeploymentAction], str, bool]] = Field(
        ..., description="Plan can include lists of actions, strings, or boolean values."
    )


class FluidityPlanPayload(BaseModel):
    deployment_plan: Dict[str, Any] = Field(..., description="Deployment plan details, allowing flexibility.")
    name: str = Field(..., description="Name of the deployment plan.")
    plan_uid: str = Field(..., description="The UUID of the plan.")

if __name__ == "__main__":

    # Input/test payload
    payload = {
    "deployment_plan": {
        "server-app": [
            {
                "action": "change_spec",
                "new_spec": {
                    "image": "harbor.nbfc.io/mlsysops/test-app:sha-90e0077",
                    "runtime_class_name": "containerd",
                    "platform_requirements": {
                        "cpu": {
                            "architecture": ["amd64"],
                            "frequency": 1.4,
                            "limits": "500m",
                            "requests": "250m"
                        },
                        "disk": "120",
                        "memory": {"limits": "128Mi", "requests": "64Mi"},
                        "performance_indicator": 30
                    },
                    "other_fields": {
                        "containers": [
                            {
                                "command": ["python", "TcpServer.py"],
                                "env": [
                                    {"name": "OTEL_RESOURCE_ATTRIBUTES", "value": "service.name=server-app, service.version=0.0.0, service.experimentid=test"},
                                    {"name": "OTEL_SERVICE_NAME", "value": "server-app"},
                                    {"name": "NODE_IP", "value_from": {"field_ref": {"field_path": "status.hostIP"}}},
                                    {"name": "TELEMETRY_ENDPOINT", "value": "$(NODE_IP):43170"},
                                    {"name": "TCP_SERVER_IP", "value": "0.0.0.0"}
                                ],
                                "ports": [{"container_port": 10000, "protocol": "TCP"}]
                            }
                        ],
                        "host_network": False,
                        "metadata": {"name": "server-app", "uid": "a9jwduj9028uje"},
                        "node_placement": {"continuum_layer": ["edge"], "mobile": True, "node": "mls-ubiw-2"},
                        "node_type": "virtualized",
                        "os": "ubuntu",
                        "qos_metrics": [
                            {
                                "application_metric_id": "test_received_success_counter_total",
                                "relation": "lower_or_equal",
                                "system_metrics_hints": ["cpu_frequency"],
                                "target": 20
                            }
                        ],
                        "restart_policy": "OnFailure",
                        "sensors": [
                            {
                                "camera": {
                                    "camera_type": "rgb",
                                    "minimum_framerate": 20,
                                    "model": "d455",
                                    "resolution": "1024x768"
                                },
                                "endpoint_variable": "CAMERA_ENDPOINT",
                                "instances": 1,
                                "protocol": "RTSP"
                            }
                        ]
                    }
                },
                "host": "mls-ubiw-2"
            }
        ],
        "initial_plan": False
    },
    "name": "test-application",
    "plan_uid": "ce803ddd-ceb7-4641-ac91-89db9f2e7d5f"
}

    # Validate the payload
    try:
        validated_payload = FluidityPlanPayload(**payload)
        logger.info("Validation successful!")
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
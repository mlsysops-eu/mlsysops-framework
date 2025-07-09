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
"""
This script includes structured representations for the Fluidity system
events by defining detailed models for each type of event payload.
It supports events such as `plan_executed`, `application_created`,
`application_updated`, `application_deleted`, and others.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from enum import Enum
from mlsysops.events import MessageEvents

# --------------- SHARED COMPONENTS --------------- #


class QoSMetrics(BaseModel):
    application_metric_id: str = Field(..., description="ID of the application-level metric.")
    relation: str = Field(..., description="Relation to evaluate the metric (e.g., 'lower' or 'greater').")
    target: int = Field(..., description="Target value for the QoS metric.")
    system_metrics_hints: Optional[List[str]] = Field(None, description="System metrics hints to track.")


# --------------- PLAN_EXECUTED EVENT COMPONENTS --------------- #


class ComponentSpec(BaseModel):
    event: MessageEvents = Field(..., description="The event related to the component.")
    hostname: str = Field(..., description="The hostname of the system managing the component.")
    pod_spec: Dict[str, Any] = Field(..., description="Generic dictionary representing the pod specifications.")


class ComponentDetails(BaseModel):
    qos_metrics: List[QoSMetrics] = Field(..., description="List of QoS metrics associated with the component.")
    specs: Dict[str, ComponentSpec] = Field(..., description="Specifications and events for individual components.")


class PlanExecutionPayload(BaseModel):
    app_uid: Optional[str] = Field(None, description="Optional unique identifier for the application.")
    comp_dict: Dict[str, ComponentDetails] = Field(..., description="Dictionary of components with their details.")
    name: str = Field(..., description="Name of the deployment plan.")
    plan_uid: str = Field(..., description="Unique identifier for the deployment plan.")
    spec: Dict[str, Any] = Field(..., description="Additional plan specifications.")
    status: Optional[str] = Field(..., description="Indicates whether the plan execution was successful.")


# --------------- APPLICATION EVENTS (CREATED, UPDATED, DELETED) COMPONENTS --------------- #


class ContainerSpecs(BaseModel):
    command: List[str] = Field(..., description="Commands to run in the container.")
    env: List[Dict[str, Any]] = Field(..., description="Environment variables for the container.")
    image: str = Field(..., description="Docker image for the container.")
    image_pull_policy: str = Field(..., description="Policy for pulling images.")
    platform_requirements: Optional[Dict[str, Any]] = Field(None, description="Resource requirements for the container.")
    ports: Optional[List[Dict[str, Any]]] = Field(None, description="List of ports exposed by the container.")


class ComponentSpecs(BaseModel):
    container_runtime: str = Field(..., description="Container runtime for the component.")
    containers: List[ContainerSpecs] = Field(..., description="List of containers within this component.")
    host_network: Optional[bool] = Field(None, description="Indicates if the component uses the host's network namespace.")
    metadata: Dict[str, Any] = Field(..., description="Metadata for the component.")
    node_placement: Dict[str, Any] = Field(..., description="Placement specifications for the component.")
    os: Optional[str] = Field(None, description="Operating system for the component.")
    restart_policy: Optional[str] = Field(None, description="Restart policy for the component.")
    sensors: Optional[List[Dict[str, Any]]] = Field(None, description="Sensor data associated with the component.")
    qos_metrics: Optional[List[QoSMetrics]] = Field(None, description="QoS specifications for workload requirements.")


class ApplicationSpec(BaseModel):
    api_version: str = Field(..., description="API version of the application.")
    cluster_placement: Dict[str, List[str]] = Field(
        ..., description="Placement specification for clusters."
    )
    component_interactions: Optional[List[Dict[str, str]]] = Field(
        None, description="Details of component interactions."
    )
    components: List[ComponentSpecs] = Field(..., description="Application component descriptions.")
    global_satisfaction: Dict[str, Any] = Field(..., description="Global satisfaction configuration.")
    kind: str = Field(..., description="The kind of application (e.g., 'MLSysOpsApp').")
    metadata: Dict[str, Any] = Field(..., description="Metadata for the application (e.g., annotations).")


class ApplicationEventPayload(BaseModel):
    app_uid: Optional[str] = Field(None, description="Application unique identifier.")
    name: str = Field(..., description="Name of the application.")
    spec: ApplicationSpec = Field(..., description="Specifications for the application.")


# --------------- NODE_SYSTEM_DESCRIPTION_SUBMITTED EVENT COMPONENTS --------------- #


class NodeSysDescSubmittedPayload(BaseModel):
    crd_plural: str = Field(..., description="Custom resource definition plural name.")
    name: str = Field(..., description="Node system name.")
    resource: str = Field(..., description="Resource affected.")
    spec: Dict[str, Any] = Field(..., description="Specifications for the node system.")
    uid: Optional[str] = Field(None, description="Unique identifier for the node system.")


# --------------- CLUSTER_SYS_DESC_SUBMITTED EVENT COMPONENTS --------------- #


class ClusterSysDescSubmittedPayload(BaseModel):
    crd_plural: str = Field(..., description="Custom resource definition plural name.")
    name: str = Field(..., description="Cluster system name.")
    resource: str = Field(..., description="Resource affected.")
    spec: Dict[str, Any] = Field(..., description="Specifications for the cluster system.")
    uid: Optional[str] = Field(None, description="Unique identifier for the cluster system.")


# --------------- KUBERNETES_NODE_ADDED EVENT COMPONENTS --------------- #


class KubernetesNodeAddedPayload(BaseModel):
    name: str = Field(..., description="Kubernetes node name.")
    resource: str = Field(..., description="Resource type for the node.")
    spec: Dict[str, Any] = Field(..., description="Specifications for the node.")
    uid: Optional[str] = Field(None, description="Unique identifier for the node.")


# --------------- POD_MODIFIED EVENT COMPONENTS --------------- #


class PodModifiedPayload(BaseModel):
    name: str = Field(..., description="Modified pod name.")
    resource: str = Field(..., description="Modified pod resource type.")
    spec: Dict[str, Any] = Field(..., description="Specifications for the modified pod.")
    uid: Optional[str] = Field(None, description="Unique identifier for the pod.")


# --------------- MAIN EVENT MODEL --------------- #


class FluidityEvent(BaseModel):
    event: MessageEvents = Field(..., description="Event type.")
    operation: Optional[str] = Field(None, description="Operation type.")
    origin: Optional[str] = Field(None, description="Origin of the event.")
    payload: Any = Field(..., description="Details of the event payload.")

    def get_payload_model(self):
        if self.event in [MessageEvents.APP_CREATED, MessageEvents.APP_UPDATED, MessageEvents.APP_DELETED]:
            return ApplicationEventPayload.model_validate(self.payload)
        elif self.event == MessageEvents.PLAN_EXECUTED:
            return PlanExecutionPayload.model_validate(self.payload)
        elif self.event == MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMITTED:
            return NodeSysDescSubmittedPayload.model_validate(self.payload)
        elif self.event == MessageEvents.CLUSTER_SYSTEM_DESCRIPTION_SUBMITTED:
            return ClusterSysDescSubmittedPayload.model_validate(self.payload)
        elif self.event == MessageEvents.KUBERNETES_NODE_ADDED:
            return KubernetesNodeAddedPayload.model_validate(self.payload)
        elif self.event == MessageEvents.POD_MODIFIED:
            return PodModifiedPayload.model_validate(self.payload)
        else:
            raise ValueError(f"Unsupported event type: {self.event}")


# --------------- EXAMPLE USAGE --------------- #


if __name__ == "__main__":
    # List of examples representing different event types
    examples = [
        # Corrected plan_executed example
        {
            "event": "plan_executed",
            "origin": None,
            "operation": None,
            "payload": {
                "app_uid": "12345",
                "comp_dict": {
                    "server-app": {
                        "qos_metrics": [
                            {
                                "application_metric_id": "test_received_success_counter",
                                "relation": "lower_or_equal",
                                "target": 20,
                                "system_metrics_hints": ["cpu_frequency"]
                            }
                        ],
                        "specs": {
                            "server-app-123": {
                                "event": "pod_modified",  # Corrected to match allowed enum values
                                "hostname": "mls-ubiw-2",
                                "pod_spec": {"apiVersion": "v1", "kind": "Pod"}
                            }
                        }
                    }
                },
                "name": "test-plan",
                "plan_uid": "plan-001",
                "spec": {},
                "status": "Completed"
            }
        },
        {
            "event": "application_created",
            "origin": None,
            "operation": None,
            "payload": {
                "app_uid": "app-12345",
                "name": "test-application-created",
                "spec": {
                    "api_version": "mlsysops.eu/v1",
                    "cluster_placement": {"cluster_id": ["mls-ubiw-1"]},
                    "component_interactions": [],
                    "components": [],
                    "global_satisfaction": {"threshold": 0.7},
                    "kind": "MLSysOpsApp",
                    "metadata": {"name": "test-app", "namespace": "mlsysops"}
                }
            }
        },
        {
            "event": "application_updated",
            "origin": None,
            "operation": None,
            "payload": {
                "app_uid": "app-12345",
                "name": "test-application-updated",
                "spec": {
                    "api_version": "mlsysops.eu/v1",
                    "cluster_placement": {"cluster_id": ["mls-ubiw-1"]},
                    "component_interactions": [],
                    "components": [],
                    "global_satisfaction": {"threshold": 0.7},
                    "kind": "MLSysOpsApp",
                    "metadata": {"name": "test-app", "namespace": "mlsysops"}
                }
            }
        },
        {
            "event": "application_deleted",
            "origin": None,
            "operation": None,
            "payload": {
                "app_uid": "app-12345",
                "name": "test-application-deleted",
                "spec": {
                    "api_version": "mlsysops.eu/v1",
                    "cluster_placement": {"cluster_id": ["mls-ubiw-1"]},
                    "component_interactions": [],
                    "components": [],
                    "global_satisfaction": {"threshold": 0.7},
                    "kind": "MLSysOpsApp",
                    "metadata": {"name": "test-app", "namespace": "mlsysops"}
                }
            }
        },
        {
            "event": "node_sys_desc_submitted",
            "origin": "internal",
            "operation": "SUBMITTED",
            "payload": {
                "crd_plural": "nodespecs",
                "name": "node-001",
                "resource": "NodeSpec",
                "spec": {"cpu": "4", "memory": "8Gi"},
                "uid": "node-uid-001"
            }
        },
        {
            "event": "cluster_sys_desc_submitted",
            "origin": "internal",
            "operation": "SUBMITTED",
            "payload": {
                "crd_plural": "clusterspecs",
                "name": "cluster-001",
                "resource": "ClusterSpec",
                "spec": {"nodes": 5, "region": "us-west"},
                "uid": "cluster-uid-001"
            }
        },
        {
            "event": "kubernetes_node_added",
            "origin": "system",
            "operation": "ADDED",
            "payload": {
                "name": "k8s-node-001",
                "resource": "KubernetesNode",
                "spec": {"role": "worker", "capacity": {"cpu": "4", "memory": "8Gi"}},
                "uid": "k8s-uid-001"
            }
        },
        {
            "event": "pod_modified",
            "origin": "internal",
            "operation": "MODIFIED",
            "payload": {
                "name": "test-pod",
                "resource": "Pod",
                "spec": {"containers": [{"name": "app-container", "image": "app-image:latest"}]},
                "uid": "pod-uid-001"
            }
        }
    ]

    # Validate and print all examples
    for example in examples:
        try:
            event = FluidityEvent(**example)
            parsed_payload = event.get_payload_model()
            print(f"Event: {example['event']}")
            print(parsed_payload.model_dump_json(indent=4))
        except Exception as e:
            print(f"Error processing event: {example['event']}")
            print(f"Exception: {str(e)}")

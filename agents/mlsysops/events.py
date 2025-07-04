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

from enum import Enum


class MessageEvents(Enum):
    # Application-specific events
    APP_CREATED = "application_created"
    APP_UPDATED = "application_updated"
    APP_DELETED = "application_deleted"
    APP_SUBMIT = "application_submitted"
    APP_REMOVED = "application_removed"
    POD_ADDED = "pod_added"
    POD_MODIFIED = "pod_modified"
    POD_DELETED = "pod_removed"

    # Infrastructure-specific events
    NODE_SYSTEM_DESCRIPTION_SUBMITTED = "node_sys_desc_submitted"
    NODE_SYSTEM_DESCRIPTION_UPDATED = "node_sys_desc_updated"
    NODE_SYSTEM_DESCRIPTION_REMOVED = "node_sys_desc_removed"
    KUBERNETES_NODE_ADDED = "kubernetes_node_added"
    KUBERNETES_NODE_MODIFIED = "kubernetes_node_modified"
    KUBERNETES_NODE_REMOVED = "kubernetes_node_removed"
    CLUSTER_SYSTEM_DESCRIPTION_SUBMITTED = "cluster_sys_desc_submitted"
    CLUSTER_SYSTEM_DESCRIPTION_UPDATED = "cluster_sys_desc_updated"
    CLUSTER_SYSTEM_DESCRIPTION_REMOVED = "cluster_sys_desc_removed"
    DATACENTER_SYSTEM_DESCRIPTION_SUBMIT = "datacemter_sys_desc_submitted"
    DATACENTER_SYSTEM_DESCRIPTION_UPDATED = "datacenter_sys_desc_updated"
    DATACENTER_SYSTEM_DESCRIPTION_REMOVED = "datacenter_sys_desc_removed"

    # Policy-specific events
    PLAN_SUBMITTED = "plan_submitted"
    PLAN_EXECUTED = "plan_executed"
    COMPONENT_PLACED = "application_component_placed"
    COMPONENT_REMOVED = "application_component_removed"
    COMPONENT_UPDATED = "application_component_updated"

    # Internal events
    OTEL_DEPLOY = "otel_deploy"
    OTEL_UPDATE = "otel_update"
    OTEL_REMOVE = "otel_remove"
    MESSAGE_TO_NODE = "message_to_node"

    PLAN_STATUS_UPDATE = "plan_status_update"
    NODE_EXPORTER_DEPLOY = "node_exporter_deploy"
    NODE_EXPORTER_REMOVE = "node_exporter_remove"
    OTEL_NODE_INTERVAL_UPDATE = "otel_node_interval_update"
    NODE_STATE_SYNC = "node_state_sync"

    # Fluidity Messages
    MESSAGE_TO_FLUIDITY = "message_to_fluidity"
    MESSAGE_TO_FLUIDITY_PROXY = "message_to_fluidity_proxy"
    FLUIDITY_INTERNAL_PLAN_UPDATE = "fluidity_plan_update"
    FLUIDITY_INTERNAL_PLAN_SUBMITTED = "fluidity_plan_submitted"
    FLUIDITY_INTERNAL_STATE_UPDATE = "fluidity_state_update"

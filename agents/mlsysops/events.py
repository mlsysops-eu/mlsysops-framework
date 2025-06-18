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
    APP_CREATED = "application_created"
    APP_UPDATED = "application_updated"
    APP_DELETED = "application_deleted"
    APP_SUBMIT = "application_submitted"
    APP_REMOVED = "application_removed"
    PLAN_SUBMITTED = "plan_submitted"
    PLAN_EXECUTED = "plan_executed"
    COMPONENT_PLACED = "application_component_placed"
    COMPONENT_REMOVED = "application_component_removed"
    RECONFIGURATION = "reconfiguration"
    DELETED = "deleted"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    OTEL_DEPLOY = "otel_deploy"
    OTEL_UPDATE = "otel_update"
    OTEL_REMOVE = "otel_remove"
    NODE_SYSTEM_DESCRIPTION_SUBMIT = "node_sys_desc_submitted"
    NODE_SYSTEM_DESCRIPTION_UPDATE = "node_sys_desc_updated"
    MESSAGE_TO_NODE = "message_to_node"
    MESSAGE_TO_FLUIDITY = "message_to_fluidity"
    PLAN_STATUS_UPDATE = "plan_status_update"
    NODE_EXPORTER_DEPLOY = "node_exporter_deploy"
    NODE_EXPORTER_REMOVE = "node_exporter_remove"

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

import copy
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Dict, Optional, List
from enum import Enum

# Define explicit values for status using an Enum
class Status(Enum):
    COMPLETED = "Completed"
    PENDING = "Pending"
    FAILED = "Failed"
    SCHEDULED = "Scheduled"
    CANCELLED = "Cancelled"
    DISCARDED = "Discarded"
    UNKNOWN = "Unknown"

@dataclass
class TaskLogEntry:
    uuid: str
    timestamp: float
    application_id: str
    task_name: str
    start_time: float
    end_time: float
    mechanism: Optional[Dict[str, str]]
    arguments: Optional[Dict[str, Any]] = None
    status: Optional[Status] = None  # e.g., "Success", "Failed"
    result: Optional[Any] = None  # Used in analysis tasks
    plan: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the dataclass into a dictionary, ensuring all fields are serializable.
        """

        def safe_serialize(value):
            try:
                return copy.deepcopy(value)
            except TypeError:
                return str(value)  # Fallback to string for non-serializable objects

        result_dict = {}
        for field in fields(self):
            value = getattr(self, field.name)
            result_dict[field.name] = safe_serialize(value)
        return result_dict
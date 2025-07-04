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

class MLSApplication:
    def __init__(self, application_id, application_description,policies=None):
        self.application_id = application_id
        self.policies = policies
        self.application_description = application_description

    def get_component_by_name(self, component_name):
        """
        Fetch a component by its name.
        Args:
            component_name (str): Name of the component to fetch.
        Returns:
            MLSComponent: The matched component or None if not found.
        """
        for component in self.components:
            if component.name == component_name:
                return component
        return None

    def update_policy(self, new_policy):
        """
        Update the active policy of the application at runtime.
        Args:
            new_policy (dict): The new policy to be applied.
        """
        self.policies = new_policy
        self.active_policy = new_policy.get("policy", None)

    def to_message(self):
        return {
            "application_id": self.application_id,
            "application_description": self.application_description,
        }
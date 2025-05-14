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

import asyncio

# from mlsysops.tasks.analyze import AnalyzeTask


class MLSApplication:
    def __init__(self, application_id, app_desc, component_spec=None, pod_spec=None,policies=None): # TODO What should we include in the general one
        self.application_id = application_id
        self.component_spec = component_spec
        self.pod_spec = pod_spec
        self.policies = policies
        self.app_desc = app_desc
        # self.active_policy = component_spec.get("policy")

        # Parse component spec into MLSComponent instances
        self.components = [
            # MLSComponent(component['name'], component['spec'])
            # for component in component_spec
        ]

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



class MLSComponent:

    def __init__(self, name, spec):
        self.name = name
        self.spec = spec
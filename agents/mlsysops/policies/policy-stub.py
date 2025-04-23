"""Plugin module for custom policies """
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

import inspect

def initialize():
    print(f"Initializing policy {inspect.stack()[1].filename}")


""" Plugin function to implement the initial deployment logic.
"""
def initial_plan(app_desc, cores):
    plan = []
    context = []
    return plan, context


def analyze_status(app_desc, cores, context, system_metrics, curr_deployment):

   return True, context



def re_plan(old_app_desc, new_app_desc, context, curr_deployment):

    return [], context

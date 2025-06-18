"""Configuration-related info.

Contains the basic configuration for the Fluidity custom resources.
"""
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

import os

#: the REST API group name
API_GROUP = 'mlsysops.eu'
#: the namespace of the custom resources
CRDS_NAMESPACE = 'default'
#: System file directory of CRDs
_CRDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../resources/manifests/templates/'))

mlsysops_node_dict = {
    'singular': 'mlsysopsnode',
    'plural': 'mlsysopsnodes',
    'kind': 'MLSysOpsNode',
    'crd_name': 'mlsysopsnodes.{}'.format(API_GROUP),
    'crd_file': '{}/MLSysOpsNode.yaml'.format(_CRDS_DIR),
    'version': 'v1'
}

mlsysops_app_dict = {
    'singular': 'mlsysopsapp',
    'plural': 'mlsysopsapps',
    'kind': 'MLSysOpsApp',
    'crd_name': 'mlsysopsapps.{}'.format(API_GROUP),
    'crd_file': '{}/MLSysOpsApplication.yaml'.format(_CRDS_DIR),
    'version': 'v1'
}

#: list: List with info regarding the supported custom resources
CRDS_INFO_LIST = [mlsysops_node_dict, mlsysops_app_dict]

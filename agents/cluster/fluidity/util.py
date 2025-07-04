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
"""FluidityApp Controller-related utilities module."""
from operator import itemgetter

def is_int(num):
    """Check if num is or can be converted to int."""
    try:
        int(num)
        return True
    except ValueError:
        return False

CONVERSION_FACTOR = {
    "k":1000, "Ki":1024,
    "M":1000000, "Mi":1048576,
    "G":1000000000, "Gi": 1073741824,
    "T":1000000000000, "Ti": 1099511627776,
    "P":1000000000000000, "Pi": 1125899906842624,
    "E":1000000000000000000, "Ei":1152921504606846976
    }

def cpu_human_to_cores(cpu_str):
    if cpu_str.endswith("m"):
        return float(cpu_str[:-1]) / 1000
        
    return float(cpu_str)

def human_to_byte(num):
    """Convert a string representation of a resource to bytes.
    
    See: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
    https://kubernetes.io/docs/reference/kubernetes-api/common-definitions/quantity/
    """
    if is_int(num):
        return int(num)
    num = str(num)
    num_idx = 0
    while num_idx < len(num):
        if str.isdigit(num[num_idx]) or num[num_idx] == '.':
            num_idx += 1
        else:
            break
    if is_int(num[:num_idx]):
        num_part = int(num[:num_idx])
    else:
        num_part = float(num[:num_idx])
    str_part = num[num_idx:].strip()
    bytes = num_part * CONVERSION_FACTOR[str_part]
    return int(bytes)


"""FluidityApp template dictionary."""
FluidityAppInfoDict = {
    'name': None, #: str: Application name
    'uid': None, #: str: Application unique identifier
    'fpath': None, #: str: Application manifests file path
    'spec': None, #: obj: Application specification
    'context': None, #: obj: App specific context for the policy
    'curr_plan': {
        'curr_deployment': {}, #: dict: The global deployment of the application,
        'enable_redirection': False, # Notifies the internal Fluidity mechanism to perform data-traffic
                                     # redirection (if possible).
        'disable_redirection': False # Notifies the internal Fluidity mechanism to stop data-traffic
                                     # redirection (if possible).
    },
    'components': {}, #: dict: Key the component name, value the (extended) description
    'total_pods': 0, #: int: Total number of created pods
    'pod_names': [] #: list of str: Names of created pods
}

"""Fluidity Component template dictionary."""
FluidityCompInfoDict = {
        'spec': None, #: dict: The original component specification
        'name': None, #: str: Component name
        'cluster_id': None, #: str: Cluster id
        'uid': None, #: str: Component unique identifier
        'labels': None, #: lst of str: labels for filtering of candidate nodes
        'qos_metrics': [], #: lst of dict: metrics along with their constraints
        'hosts': [], #: lst of dict: Selected host(s) for drone/edge components
        'pod_template': None, #: dict: Component's Pod manifest template
        'pod_object': None, #: obj: Component's Pod object model template
        'pod_names': [], #: list of str: Names of the component's Pods
        'pod_manifests': [], #: list of dict: Component's actual Pod manifests
        'pod_fpaths': [], #: list of str: Filepaths to the Pod manifest files
        'svc_manifest': None, #: dict: Component's Service manifest
        'svc_object': None, #: obj: Component's Service object model
        'svc_fpath': None, #: str: Filepath to the service manifest file
        'svc_vip': None, #: str: The Virtual IP of the exposed service
        'svc_port': None, #: str: The port of the exposed service
        #: dict: Requested node resources
        'resources_requests': {
            'cpu': 0.0,
            'memory': 0
        },
        #: dict: Limits on node resources
        'resources_limits': {
            'cpu': 0.0,
            'memory': 0
        }
}
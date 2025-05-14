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


def sort_linked_list(list1, list2, reverse=False):
    """Sort list1 based on sorted indices of list2."""
    #from more_itertools import sort_together
    # l3 = [x for _,x in sorted(zip(l2, l1))]
    list3 = [x for (y,x) in sorted(zip(list2,list1), key=lambda pair: pair[0], reverse=reverse)]
    return list3


def get_sorted_indices(l_origin, reverse=False):
    """Retrieve indices of the ordered list."""
    enumerate_object = enumerate(l_origin)
    sorted_pairs = sorted(enumerate_object, key=itemgetter(1), reverse=reverse)
    sorted_indices = []
    for index, element in sorted_pairs:
        sorted_indices.append(index)
    # sorted_indices = [index for index, element in sorted_pairs]
    return sorted_indices


def is_float(num):
    """Check if num is or can be converted to float."""
    try:
        float(num)
        return True
    except ValueError:
        return False


def is_int(num):
    """Check if num is or can be converted to int."""
    try:
        int(num)
        return True
    except ValueError:
        return False


def is_number(num):
    try:
        complex(num) # for int, long, float and complex
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


def human_to_byte(num):
    """Convert a string representation of a resource to bytes.
    
    See: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
    https://kubernetes.io/docs/reference/kubernetes-api/common-definitions/quantity/
    """
    if is_int(num):
        return int(num)
    # if is_float(num):
    #     return float(num)
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


FluidityNodeInfoDict = {
    'cloudnodes': [],
    'edgenodes': [],
    'mobilenodes': [],
    'drones': [],
    'dronestations': [],
    'k8snodes': []
}

FluidityAppInfoDict = {
    'name': None, #: str: Application name
    'uid': None, #: str: Application unique identifier
    'fpath': None, #: str: Application manifests file path
    'spec': None, #: obj: Application specification
    'context': None, #: obj: App specific context for the policy
    'plugin_policy': None, #: obj: App specific plugin policy
    'velocity_q': None, # queue of floats, containing the last X velocity values
    'statistics': {}, # Dictionary of dictionaries, 
                           # 'key' is the node name
                           # 'value' is a dict of the following form:
                           # {
                           #    'AvgCallDelay': 0.0,
                           #    'RawCallDelays': [],
                           #    'TotalCalls':0,
                           #    'CurrentSum': 0.0,
                           #    'lastEntrance': 0,
                           #    'lastExit': 0,
                           #    'MigrateFrom': {} # Dict of dicts containing
                           #                         # all the required info about a migration
                           #                         # Each entry of the dict has the following
                           #                         # structure.
                           #    'key' of each dict is "src->dst"
                           #    'value' has the following form: 
                           #        {                     
                           #        'AvgAdaptDelay': 0.0,
                           #        'RawAdaptDelays': [],
                           #        'CurrentSum': 0.0,
                           #        'TotalAdaptations':0
                           #        }
                           # }
    'curr_plan': {
        'curr_deployment': {
            # to be emptied 
            # comp1: {
            #     'Deploy': None,
            #     'Remove': None,
            #     'Move': {
            #         'src': None,
            #         'dst': None
            #     }
            #    }
        }, #: dict: The global deployment of the application,
                           # key the component, value the respecive host(s)
        'enable_redirection': False, # Notifies the internal Fluidity mechanism to perform data-traffic
                                     # redirection (if possible).
        'disable_redirection': False # Notifies the internal Fluidity mechanism to stop data-traffic
                                     # redirection (if possible).
    },
    'last_transition': None, # The last timestamp that refers to a region change (not necessarily migration)
    'reachable_edgenodes': {}, # NOTE: Should be moved to another structure.
    'proximity_list': [], # Used by the policy plugins to store info about proximity
    # of edge nodes with respect to the mobile node.
    'state': 'INITIALIZATION', #'AREA-CALCULATION' #: str: Current deployment state
    'has_driver': False, #: bool: True if app has driver
    'driver_name': None, #: str: Name of the driver component
    'driver_spec': None, #: obj: Specification of the driver component
    'passenger_names': [], #: list of str: Names of passenger components
    'passenger_specs': [], #: list of obj: Specifications of passenger components
    'has_chauffeur': False, #: bool: True if system chauffeur controls the drone
    'chauffeur_info': None, #: obj: The POIs field to be used by a chauffeur
    'drone_comp_names': [], #: list of str: Names of all driver and passenger components
    'edge_comp_names': [], #: list of str: Names of static edge components
    'edge_comp_specs': [], #: list of obj: Specifications of static edge components
    'edge_infra_comp_names': [], #: list of str: Names of static edge infra components
    'edge_infra_comp_specs': [], #: list of obj: Specifications of static edge infra components
    'far_edge_comp_names': [], #: list of str: Names of static edge components
    'far_edge_comp_specs': [], #: list of obj: Specifications of static edge components
    'hybrid_comp_names': [], #: list of str: Names of hybrid components
    'hybrid_comp_specs': [], #: list of obj: Specifications of hybrid components
    'hybrid_drone_comp_names': [], #: list of str: Names of hybrid to drone components
    'hybrid_edge_comp_names': [], #: list of str: Names of hybrid to static components
    'hybrid_mobile_comp_names': [], #: list of str: Names of hybrid to mobile components
    'cloud_comp_names': [], #: list of str: Names of cloud components
    'cloud_comp_specs': [], #: list of obj: Specifications of cloud components
    'mobile_comp_names': [], #: list of str: Names of mobile components
    'mobile_comp_specs': [], #: list of obj: Specifications of mobile components
    'components': {}, #: dict: Key the component name, value the (extended) description
    'drone_candidates': [], #: list: Names of drone candidates
    'drone_candidates_scores': [], #: list: Scores of drone candidates
    'drone_op_area': None, #: obj: Calculated drone operation area
    'drone_com_area': None, #: obj: Calculated drone direct communication area
    #: dict: Total requested drone resources (driver+passengers)
    'drone_resources_requests': {
        'cpu': 0.0,
        'memory': 0
    },
    #: dict: Total limits on drone resources (driver+passengers)
    'drone_resources_limits': {
        'cpu': 0.0,
        'memory': 0
    },
    'total_pods': 0, #: int: Total number of created pods
    'pod_names': [] #: list of str: Names of created pods
}
"""FluidityApp template dictionary."""
#: NOTE: Once finalized introduce it with a FluidityAppInfo class


FluidityCompInfoDict = {
        'spec': None, #: dict: The original component specification
        'name': None, #: str: Component name
        'cluster_id': None, #: str: Cluster id
        'uid': None, #: str: Component unique identifier
        'labels': None, #: lst of str: labels for filtering of candidate nodes
        'qos_metrics': [], #: lst of dict: metrics along with their constraints
        'candidates': [], #: lst of str: Location-based candidate nodes
        'candidates_scores': [], #: lst of str: Scores of candidate nodes
        'hosts': [], #: lst of dict: Selected host(s) for drone/edge components
        'current_pod_ip': None, # Used for fast lookups, it will be moved to be pod-specific
        'op_area': None, #: obj: Calculated component operation area
        'is_drone_interacting': False, #: bool: True if interacts with a drone component
        'is_mobile_interacting': False, #: bool: True if interacts with a mobile component
        'edge_interacting': [], # list of str: Names of all static edge interacting components
        'ingressDrone': [], #: list of str: Names of ingress drone components
        'ingressEdge': [], #: list of str: Names of ingress (static) edge components
        'ingressEdgeInfra': [], #: list of str: Names of ingress (static) edgeInfra components
        'ingressFarEdge': [], #: list of str: Names of ingress (static) FarEdge components
        'ingressHybrid': [], #: list of str: Names of ingress hybrid components
        'ingressCloud': [], #: list of str: Names of ingress cloud components
        'ingressMobile': [], #: list of str: Names of ingress mobile components
        'egressDrone': [], #: list of str: Names of egress drone components
        'egressEdge': [], #: list of str: Names of egress (static) edge components
        'egressEdgeInfra': [], #: list of str: Names of ingress (static) edgeInfra components
        'egressFarEdge': [], #: list of str: Names of ingress (static) FarEdge components
        'egressHybrid': [], #: list of str: Names of egress hybrid components
        'egressCloud': [], #: list of str: Names of egress cloud components
        'egressMobile': [], # list of str: Names of egress mobile components
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
"""Fluidity Component template dictionary."""
#: NOTE: Once finalized introduce it with a FluidityCompInfo class


HybridDroneInfoDict = {
        'candidates_hybrid_drone': [], #: list of str: Location-based candidate nodes
        'candidates_hybrid_drone_intersection': [], #: list of obj: Intersection area of candidate nodes
        'candidates_hybrid_drone_coverage': [], #: list of float: Coverage of candidate nodes
        'hosts_hybrid_drone': [], #: list of str: Selected hosts
        'hosts_hybrid_drone_intersection': [], #: list of obj: Intersection area of hosts
        'hosts_hybrid_drone_coverage': [], #: list of float: Coverage of hosts
        'host_hybrid_cloud': None #: str: Selected host of cloud instance
}
"""Dictionary with extra fields for hybrid components."""
#: NOTE: This is appended to an instance of the FluidityCompInfoDict

HybridMobileInfoDict = {
        'current_mobile_loc': [0.0, 0.0], # Current mobile coordinates
        'previous_mobile_loc': [0.0, 0.0], # Previous mobile coordinates, used to calc the chord for the 2nd policy
        'velocity': 0.0, # NOTE: Not needed, to be removed later.
        'candidates_hybrid_mobile': [], #: list of str: Location-based candidate nodes
        'candidates_hybrid_mobile_proximity': [], #: list of float: Proximity between candidate nodes and mobile node
        'hosts_hybrid_mobile': [], #: list of str: Selected hosts
        'hosts_hybrid_mobile_proximity': [], #: list of obj: Proximity of hosts
        'host_hybrid_cloud': None #: str: Selected host of cloud instance
}
"""Dictionary with extra fields for hybrid components."""
#: NOTE: This is appended to an instance of the FluidityCompInfoDict

HybridEdgeInfoDict = {
        #: dict: Key name of static edge component, value dict with key static interacting component and value
        'candidates_hybrid_edge': {},
        'candidates_hybrid_edge_intersection': {}, #: dict: The communication intersection areas
        'candidates_hybrid_edge_coverage': {}, #: dict: Achieved coverage (the score)
        'hosts_hybrid_edge': [], #: list of str: Selected hosts
        'related_hosts_hybrid_edge': [], #: list of str: Node names of related static edge instance
        'host_hybrid_cloud': None #: str: Selected host of cloud instance   
}
"""Dictionary with extra fields for hybrid components."""
#: NOTE: This is appended to an instance of the FluidityCompInfoDict

FluidityPolicyAppInfoDict = {
    'name': None, #: str: Application name
    'uid': None, #: str: Application unique identifier
    'fpath': None, #: str: Application manifests file path
    'spec': None, #: obj: Application specification
    'nodes': {}, #: Dict: Custom dictionary for the policy to store the nodes for re_plan() invocation.
    'velocity_q': None, # queue of floats, containing the last X velocity values
    'updated_resources': {},
    'model_info': None,
    'statistics': {}, # Dictionary of dictionaries, 
                           # 'key' is the node name
                           # 'value' is a dict of the following form:
                           # {
                           #    'AvgCallDelay': 0.0,
                           #    'RawCallDelays': [],
                           #    'TotalCalls':0,
                           #    'CurrentSum': 0.0,
                           #    'lastEntrance': 0,
                           #    'lastExit': 0,
                           #    'MigrateFrom': {} # Dict of dicts containing
                           #                         # all the required info about a migration
                           #                         # Each entry of the dict has the following
                           #                         # structure.
                           #    'key' of each dict is "src->dst"
                           #    'value' has the following form: 
                           #        {                     
                           #        'AvgAdaptDelay': 0.0,
                           #        'RawAdaptDelays': [],
                           #        'CurrentSum': 0.0,
                           #        'TotalAdaptations':0
                           #        }
                           # }
    'curr_plan': {
        'curr_deployment': {}, #: dict: The global deployment of the application,
                           # key the component, value the respecive host(s)
        'enable_redirection': False, # Notifies the internal Fluidity mechanism to perform data-traffic
                                     # redirection (if possible).
        'disable_redirection': False # Notifies the internal Fluidity mechanism to stop data-traffic
                                     # redirection (if possible).
    },
    'last_transition': None, # The last timestamp that refers to a region change (not necessarily migration)
    'reachable_edgenodes': {}, # NOTE: Should be moved to another structure.
    'proximity_list': [], # Used by the policy plugins to store info about proximity
    # of edge nodes with respect to the mobile node.
    'state': 'INITIALIZATION', #'AREA-CALCULATION' #: str: Current deployment state
    'has_driver': False, #: bool: True if app has driver
    'driver_name': None, #: str: Name of the driver component
    'driver_spec': None, #: obj: Specification of the driver component
    'passenger_names': [], #: list of str: Names of passenger components
    'passenger_specs': [], #: list of obj: Specifications of passenger components
    'has_chauffeur': False, #: bool: True if system chauffeur controls the drone
    'chauffeur_info': None, #: obj: The POIs field to be used by a chauffeur
    'drone_comp_names': [], #: list of str: Names of all driver and passenger components
    'edge_comp_names': [], #: list of str: Names of static edge components
    'edge_comp_specs': [], #: list of obj: Specifications of static edge components
    'hybrid_comp_names': [], #: list of str: Names of hybrid components
    'hybrid_comp_specs': [], #: list of obj: Specifications of hybrid components
    'hybrid_drone_comp_names': [], #: list of str: Names of hybrid to drone components
    'hybrid_edge_comp_names': [], #: list of str: Names of hybrid to static components
    'hybrid_mobile_comp_names': [], #: list of str: Names of hybrid to mobile components
    'cloud_comp_names': [], #: list of str: Names of cloud components
    'cloud_comp_specs': [], #: list of obj: Specifications of cloud components
    'mobile_comp_names': [], #: list of str: Names of mobile components
    'mobile_comp_specs': [], #: list of obj: Specifications of mobile components
    'components': {}, #: dict: Key the component name, value the (extended) description
    'drone_candidates': [], #: list: Names of drone candidates
    'drone_candidates_scores': [], #: list: Scores of drone candidates
    'drone_op_area': None, #: obj: Calculated drone operation area
    'drone_com_area': None, #: obj: Calculated drone direct communication area
    #: dict: Total requested drone resources (driver+passengers)
    'drone_resources_requests': {
        'cpu': 0.0,
        'memory': 0
    },
    #: dict: Total limits on drone resources (driver+passengers)
    'drone_resources_limits': {
        'cpu': 0.0,
        'memory': 0
    },
    'total_pods': 0, #: int: Total number of created pods
    'pod_names': [], #: list of str: Names of created pods
    'FSM': None, # obj, Application-specific FSM.
    'iteration': 0, # Just for testing reasons.
    'prev_cmd': None, # Just for testing reasons.
    'curr_cmd': None,
    'prev_state': None, # Just for testing reasons.
    'transition_result': None, # Just for testing reasons.
    'prev_snapshot': None # To store the previous system snapshot.
}
"""FluidityApp template dictionary."""
#: NOTE: Once finalized introduce it with a FluidityAppInfo class
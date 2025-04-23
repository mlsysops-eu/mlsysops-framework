"""Configuration-related info.

Contains the basic configuration for the Fluidity custom resources.
"""
import os

#: the REST API group name
API_GROUP = 'fluidity.gr'
#: the namespace of the custom resources
CRDS_NAMESPACE = 'default'
#: System file directory of CRDs
_CRDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../resources/manifests/official_mlsysops_descriptions/templates/'))

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

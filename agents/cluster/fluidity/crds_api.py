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
"""
CRUD operations to Fluidity custom objects at the Kubernetes cluster.
"""
from __future__ import print_function
# import json
import logging
import os
# import sys

from kubernetes import client, config #, watch
from kubernetes.client.rest import ApiException
from ruamel.yaml import YAML

from crds_config import CRDS_INFO_LIST
# from fluidity_config import API_GROUP, CRDS_NAMESPACE
from objects_util import get_crd_info


logger = logging.getLogger(__name__)


class FluidityCrdsApiException(Exception):
    """Kubernetes CRDs API related errors"""
    # pass


def list_crds():
    """Return a list of CRD names registered in the Kubernetes cluster."""
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()

    ext_api = client.ApiextensionsV1Api()
    crds = []
    try:
        crds = ext_api.list_custom_resource_definition().to_dict()['items']
    except ApiException as exc:
        logger.exception('list crd failed: %s', exc)
    crds_names = [x['spec']['names']['singular'] for x in crds]
    return crds_names


def register_fluidity_crd(name):
    """Registers a Fluidity CRD."""
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()

    found, crd_info = get_crd_info(name)
    if not found:
        logger.error('Invalid resource type: %s', name)
        return False

    ext_api = client.ApiextensionsV1Api()
    # retrieve the names of registered custom resource definitions
    current_crds = []
    try:
        current_crds = ext_api.list_custom_resource_definition().to_dict()['items']
    except ApiException as exc:
        logger.exception('list crd failed: %s', exc)
        
    current_crds_names = [x['spec']['names']['singular'] for x in current_crds]

    if crd_info['singular'] in current_crds_names:
        logger.info('Fluidity CRD: %s already exists', crd_info['kind'])
        return False

    logger.info('Creating Fluidity CRD: %s', crd_info['kind'])
    try:
        yaml = YAML(typ='safe')
        with open(crd_info['crd_file'], 'r') as data:
            body = yaml.load(data)
    except IOError:
        logger.error('Resource definition not in dir %s.', crd_info['crd_file'])
        return False
    try:
        ext_api.create_custom_resource_definition(body)
    except ApiException as exc:
        logger.exception('%s update failed: %s', crd_info['kind'], exc)
        raise FluidityCrdsApiException from exc
    return True


def register_all_fluidity_crd():
    """Registers all Fluidity CRDs."""
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()
    ext_api = client.ApiextensionsV1Api()
    # retrieve the names of registered custom resource definitions
    current_crds = []
    try:
        current_crds = ext_api.list_custom_resource_definition().to_dict()['items']
    except ApiException as exc:
        logger.exception('list crd failed: %s', exc)
    current_crds_names = [x['spec']['names']['singular'] for x in current_crds]
    print(current_crds_names)

    for crd_info in CRDS_INFO_LIST:
        if crd_info['singular'] not in current_crds_names:
            logger.info('Creating Fluidity CRD: %s', crd_info['kind'])
            print('Creating Fluidity CRD: %s' % crd_info['kind'])
            try:
                yaml = YAML(typ='safe')
                with open(crd_info['crd_file'], 'r') as data:
                    body = yaml.load(data)
            except IOError:
                logger.error('Resource %s definition not in dir %s.',
                    crd_info['kind'], crd_info['crd_file'])
                continue
            try:
                ext_api.create_custom_resource_definition(body)
            except ApiException as exc:
                logger.exception('%s update failed: %s', crd_info['kind'], exc)
                print('%s update failed: %s' % (crd_info['kind'], exc))
                raise FluidityCrdsApiException from exc

        # update existing CRD
        # if crd_info['singular'] in current_crds_names:
        #     logger.info('Updating Fluidity CRD: %s', crd_info['kind'])
        #     crd = ext_api.read_custom_resource_definition(crd_info['crd_name'])
        #     crd_dict = crd.to_dict()
        #     # crd['spec']
        #     # v1 = crd.spec.versions[0]
        #       v1.schema
        #     try:
        #         yaml = YAML(typ='safe')
        #         with open(crd_info['crd_file'], 'r') as data:
        #             body = yaml.load(data)
        #         crd_dict['spec'] = body['spec']
        #         crd.spec = body['spec']
        #         ext_api.replace_custom_resource_definition(
        #             crd_info['crd_name'],
        #             crd)
        #             # crd_dict)
        #     except IOError:
        #         logger.error('Resource %s definition not in dir %s.',
        #             crd_info['kind'], crd_info['crd_file'])
        #         continue

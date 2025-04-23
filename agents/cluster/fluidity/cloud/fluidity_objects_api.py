#/usr/bin/python3
"""
CRUD operations to Fluidity custom objects at the Kubernetes cluster.
"""
from __future__ import print_function
import logging
import os

from kubernetes import client, config #, watch
from kubernetes.client.rest import ApiException

from fluidity_crds_config import API_GROUP, CRDS_NAMESPACE
from fluidity_objects_util import get_crd_info


logger = logging.getLogger(__name__)


class FluidityApiException(Exception):
    """Kubernetes API related errors"""
    # pass


class FluidityObjectsApi():
    """Fluidity-provided CRDs CRUD operations."""

    def __init__(self, api_client=None):
        if api_client is None:
            # detect if controller is run within a pod or outside
            if 'KUBERNETES_PORT' in os.environ:
                config.load_incluster_config()
            else:
                config.load_kube_config()
        # self.cr_api = client.CustomObjectsApi(api_client)
        self.cr_api = client.CustomObjectsApi() #: custom resources API client

    def list_fluidity_object(self, plural, field_select=None, label_select=None):
        """List custom fluidity resource objects"""
        _, crd_info = get_crd_info(plural)
        # cr_api = client.CustomObjectsApi()
        try:
            if label_select is None and field_select is None:
                crs = self.cr_api.list_namespaced_custom_object(
                    API_GROUP,
                    crd_info['version'],
                    CRDS_NAMESPACE,
                    plural)
                return crs
            elif label_select != None:
                crs = self.cr_api.list_namespaced_custom_object(
                    API_GROUP,
                    crd_info['version'],
                    CRDS_NAMESPACE,
                    plural,
                    label_selector=label_select,
                    pretty='true')
                return crs
        except ApiException as exc:
            logger.exception('%s retrieval failed: %s', crd_info['kind'], exc)
            raise FluidityApiException from exc

    def create_fluidity_object(self, plural, cr_body):
        """Create custom fluidity resource object"""
        _, crd_info = get_crd_info(plural)
        # cr_api = client.CustomObjectsApi()
        try:
            self.cr_api.create_namespaced_custom_object(
                API_GROUP,
                crd_info['version'],
                CRDS_NAMESPACE,
                plural,
                cr_body)
        except ApiException as exc:
            logger.exception('%s creation failed: %s', crd_info['kind'], exc)
            raise FluidityApiException from exc

    def get_fluidity_object(self, plural, name):
        """Retrieve custom fluidity resource object"""
        _, crd_info = get_crd_info(plural)
        # cr_api = client.CustomObjectsApi()
        try:
            cri = self.cr_api.get_namespaced_custom_object(
                API_GROUP,
                crd_info['version'],
                CRDS_NAMESPACE,
                plural,
                name)
            return cri
        except ApiException as exc:
            logger.exception('%s retrieval failed: %s', crd_info['kind'], exc)
            raise FluidityApiException from exc

    def update_fluidity_object(self, plural, name, cr_body):
        """Update custom fluidity resource object"""
        _, crd_info = get_crd_info(plural)
        # cr_api = client.CustomObjectsApi()
        try:
            cri = self.cr_api.replace_namespaced_custom_object(
                API_GROUP,
                crd_info['version'],
                CRDS_NAMESPACE,
                plural,
                name,
                cr_body)
            return cri
        except ApiException as exc:
            # message = jsonify('{} update failed: {}'.format(crd_info['kind'], exc))
            # raise FluidityApiException(message)
            logger.exception('%s update failed: %s', crd_info['kind'], exc)
            raise FluidityApiException from exc

    def delete_fluidity_object(self, plural, name):
        """Delete custom fluidity resource object"""
        _, crd_info = get_crd_info(plural)
        # cr_api = client.CustomObjectsApi()
        try:
            self.cr_api.delete_namespaced_custom_object(
                API_GROUP,
                crd_info['version'],
                CRDS_NAMESPACE,
                plural,
                name)
        except ApiException as exc:
            logger.exception('%s deletion failed: %s', crd_info['kind'], exc)
            raise FluidityApiException from exc

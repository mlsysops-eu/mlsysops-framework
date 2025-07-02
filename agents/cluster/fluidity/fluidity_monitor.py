"""FluidityApp monitor module."""
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

from __future__ import print_function

import asyncio
import copy
import logging
import os
import cluster_config
from cluster_config import CRDS_INFO_LIST, API_GROUP, VERSION
import kubernetes_asyncio
import watcher

from mlsysops.logger_util import logger

def find_updated_entries(new_list, old_list):
    """Checks for new/updated fluidity resources"""
    return [x for x in new_list if x not in old_list]

def contains_type(app, type):
    for comp_name in app['components']:
            comp_spec = app['components'][comp_name]
            # Check for "type" placement components
            if comp_spec['placement'] == type:
                return True
    return False


class FluidityMonitor():
    """Monitor the application execution."""

    def __init__(self, notification_queue, app=None):
        if app is None:
            self.mode = 'system'
            # We do not watch for mlsysopsapps in the monitor
            self._system_task_array = [None]*(len(CRDS_INFO_LIST))
        else:
            self.mode = 'app'
            self.app = app
            self.name = app['name']
            self._app_resource_checker_task = None
        
        # Used for communication with SPADE's fluidity msg listener
        self.notification_queue = notification_queue
        self.v1_api = kubernetes_asyncio.client.CoreV1Api()
        self.crd_api = kubernetes_asyncio.client.CustomObjectsApi()

    async def _check_for_app_resources(self):
        """Check for resource changes and add resource updates to the notification_queue."""
        app_name = self.app['name']
        logger.info(f'Resource checker thread started {app_name}')
        label_selector = 'mlsysops.eu/app='+app_name

        try:
            watcher_obj = watcher.ResourceWatcher(
                list_func= self.v1_api.list_namespaced_pod,
                resource_description="Pod",
                notification_queue = self.notification_queue,
                query_kwargs={
                    'namespace': cluster_config.NAMESPACE,
                    'label_selector': label_selector
                }
            )

            # Run watcher inside a cancellable task
            watcher_task = asyncio.create_task(watcher_obj.run())
            await watcher_task
        
        except Exception as e:
            logger.error('Unexpected exception encountered: %s', e)
        except asyncio.CancelledError:
            logger.info("Watcher task cancelled cleanly.")

        logger.info('Resource checker exiting.')

    async def _check_for_system_resources(self, resource_description):
        """Check for resource changes and add resource updates to the notification_queue."""
        logger.info(f'System Monitor task started for resource {resource_description}')
        try:
            if resource_description != 'Node':
                crd_plural = resource_description
                resource_description = 'CRD'
                logger.info(f'resource_description {resource_description}, crd_plural {crd_plural}')
                
                list_func = lambda **kwargs: self.crd_api.list_namespaced_custom_object(
                    group=API_GROUP,
                    version=VERSION,
                    namespace=cluster_config.NAMESPACE,
                    plural=crd_plural,
                    **kwargs
                ) 

            else:
                logger.info(f'resource_description {resource_description}')
                list_func = self.v1_api.list_node
                crd_plural = None

            watcher_obj = watcher.ResourceWatcher(
                list_func=list_func,
                resource_description=resource_description,
                notification_queue=self.notification_queue,
                crd_plural=crd_plural
            )

            # Run watcher inside a cancellable task
            watcher_task = asyncio.create_task(watcher_obj.run())
            await watcher_task
        except kubernetes_asyncio.client.exceptions.ApiException as exc:
            logger.error(f'exception for CRD {crd_plural} encountered: {exc}')
        except Exception as e:
            logger.error(f'Unexpected exception for CRD {crd_plural} encountered: {e}')
        except asyncio.CancelledError:
            logger.info("Watcher task cancelled cleanly.")

        logger.info('Resource checker exiting.')
    
    async def run(self):
        """Main thread function."""
        system_task_len = len(CRDS_INFO_LIST)
        if self.mode == 'system':
            for i in range(0, system_task_len):
                resource_name = CRDS_INFO_LIST[i]['plural']
                if resource_name == 'mlsysopsapps':
                    resource_name = 'Node'
                self._system_task_array[i] = asyncio.create_task(self._check_for_system_resources(resource_name))
        else:
            self._app_resource_checker_task = asyncio.create_task(self._check_for_app_resources())
        
        while True:
            try:
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                break
        
        if self.mode == 'system':
            for i in range(0, system_task_len):
                self._system_task_array[i].cancel()
        else:
            self._app_resource_checker_task.cancel()

        logger.info('Monitor\'s run() exiting.')

    async def stop(self):
        """Kill threads."""
        logger.info('AppMonitor stopped')

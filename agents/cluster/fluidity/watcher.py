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

"""Fluidity watcher for Kubernetes-related resources (CRDs/Nodes/Pods with labels)."""

import asyncio
import signal
import logging 
from kubernetes import client
import kubernetes_asyncio
from mlsysops.events import MessageEvents
import copy

from mlsysops.logger_util import logger

class ResourceWatcher:
    def __init__(self, list_func, resource_description, notification_queue, query_kwargs=None, crd_plural=None):
        self.list_func = list_func
        self.resource_description = resource_description
        self.notification_queue = notification_queue
        self.query_kwargs = query_kwargs or {}
        self.crd_plural = crd_plural
        self._stop_event = asyncio.Event()        
        self._watch_stream = None
    
    async def get_resource_version(self):
        resp = None
        
        try:
            resp = await self.list_func(**self.query_kwargs)
        
        except kubernetes_asyncio.client.exceptions.ApiException as e:
            logger.debug(f"Unhandled ApiException: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"Unhandled Exception: {e}")
            await asyncio.sleep(1)
        
        # Handle both dict (CustomObjectsApi) and model object (CoreV1Api)
        if self.resource_description == 'CRD':
            return resp['metadata']['resourceVersion']
        else:
            return resp.metadata.resource_version

    async def run(self):
        resource_version = None
        if self.resource_description == 'CRD':
            logger.info(f'CRD plural {self.crd_plural}')
            
        while not self._stop_event.is_set():
            try:
                w = kubernetes_asyncio.watch.Watch()
                self._watch_stream = w
                # build stream kwargs
                stream_kwargs = dict(
                    resource_version=resource_version or '',
                    timeout_seconds=60,
                    **self.query_kwargs
                )
                
                async with w.stream(self.list_func, **stream_kwargs) as stream:
                    async for event in stream:
                        operation = event['type']
                        obj = event['object']
                        metadata = self._extract_metadata(obj)
                        resource_version = metadata['resourceVersion']
                        name = metadata.get('name')
                        uid = metadata.get('uid')
                        
                        logger.info(f"Event: {operation} - {self.resource_description}: {name}, plural {self.crd_plural}")

                        msg = {
                            'operation': operation,
                            'origin': 'internal',
                            'payload': {
                                'name': name,
                                'uid': uid,
                                'resource': self.resource_description if self.resource_description != 'CRD' else self.crd_plural,
                                'spec': obj if isinstance(obj, dict) else obj.to_dict()
                            }
                        }

                        match self.resource_description:
                            case 'Pod':
                                logger.info('Pod resource event')
                                match operation:
                                    case 'ADDED':
                                        msg['event'] = MessageEvents.POD_ADDED.value
                                    case 'MODIFIED':
                                        msg['event'] = MessageEvents.POD_MODIFIED.value
                                    case 'DELETED':
                                        msg['event'] = MessageEvents.POD_DELETED.value
                                    case _:
                                        logger.info('kubernetes nodes unknown event.')
                            case 'Node':
                                logger.info('Node resource event')
                                match operation:
                                    case 'ADDED':
                                        msg['event'] = MessageEvents.KUBERNETES_NODE_ADDED.value
                                    case 'MODIFIED':
                                        msg['event'] = MessageEvents.KUBERNETES_NODE_MODIFIED.value
                                    case 'DELETED':
                                        msg['event'] = MessageEvents.KUBERNETES_NODE_REMOVED.value
                                    case _:
                                        logger.info('kubernetes nodes unknown event.')
                            case 'CRD':
                                logger.info(f'CRD resource event {self.crd_plural}')
                                msg['payload']['crd_plural'] = self.crd_plural
                                match self.crd_plural:
                                    case 'mlsysopsapps':
                                        logger.info('MLSysOpsApp resource event')
                                        match operation:
                                            case 'ADDED':
                                                msg['event'] = MessageEvents.APP_CREATED.value
                                            case 'MODIFIED':
                                                msg['event'] = MessageEvents.APP_UPDATED.value
                                            case 'DELETED':
                                                msg['event'] = MessageEvents.APP_DELETED.value
                                            case _:
                                                logger.info('mlsysopsnodes unknown event.')
                                    case 'mlsysopsnodes':
                                        logger.info('MLSysOpsNode resource event')
                                        match operation:
                                            case 'ADDED':
                                                msg['event'] = MessageEvents.NODE_SYSTEM_DESCRIPTION_SUBMITTED.value
                                            case 'MODIFIED':
                                                msg['event'] = MessageEvents.NODE_SYSTEM_DESCRIPTION_UPDATED.value
                                            case 'DELETED':
                                                msg['event'] = MessageEvents.NODE_SYSTEM_DESCRIPTION_REMOVED.value
                                            case _:
                                                logger.info('mlsysopsnodes unknown event.')
                                    case 'mlsysopsclusters':
                                        logger.info('MLSysOpsNode resource event')
                                        match operation:
                                            case 'ADDED':
                                                msg['event'] = MessageEvents.CLUSTER_SYSTEM_DESCRIPTION_SUBMITTED.value
                                            case 'MODIFIED':
                                                msg['event'] = MessageEvents.CLUSTER_SYSTEM_DESCRIPTION_UPDATED.value
                                            case 'DELETED':
                                                msg['event'] = MessageEvents.CLUSTER_SYSTEM_DESCRIPTION_REMOVED.value
                                            case _:
                                                logger.info('mlsysopsclusters unknown event.')
                                    case _:
                                        logger.info(f"Unknown CRD type: {event}")
                            case _:
                                logger.info(f"Unknown resource type: {event}")
                        await self.notification_queue.put(msg)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down watcher.")
                break
            except kubernetes_asyncio.client.exceptions.ApiException as e:
                if e.status == 410:
                    logger.debug("Resource version too old (410). Resetting resource version.")
                    resource_version = await self.get_resource_version()
                    await asyncio.sleep(1)
                else:
                    logger.debug(f"Unhandled ApiException: {e}")
                    await asyncio.sleep(1)
            except Exception as e:
                logger.debug(f"Unhandled Exception: {e}")
                await asyncio.sleep(1)
            finally:
                await self.close_watch()

        logger.debug("Watcher shutting down...")

    def _extract_metadata(self, obj):
        if self.resource_description == 'CRD':
            metadata = obj['metadata']
            return {
                'name': metadata['name'],
                'resourceVersion': metadata['resourceVersion']
            }
        else:
            metadata = obj.metadata
            return {
                'name': metadata.name,
                'resourceVersion': metadata.resource_version
            }

    async def close_watch(self):
        if self._watch_stream:
            try:
                self._watch_stream.stop()
            except Exception as e:
                logger.debug(f"Unhandled Exception: {e}")
            self._watch_stream = None

    def stop(self):
        logger.info("Watcher received stop signal.")
        self._stop_event.set()

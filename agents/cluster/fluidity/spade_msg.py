import copy
import logging
from mlsysops import MessageEvents

from mlsysops.logger_util import logger

PodDict = {
    'hostname': '', # host name
    'pod_spec': '', # actual pod spec
    'event': None # Component place/removed/updated
}

CompDict = {
    'specs': {},  #: dict: keys are the pod names (including uids)), value is the respective of PodDict.
    'qos_metrics': [] #: list of dict: the app metrics related to the component.
}

EventDict = {
    'event': None,  #: list of dict: the app metrics related to the component.
    'payload': {
        'name': '', #: str: The application name.
        'spec': {}, #: dict: The application specification.
        'status': '', #: str: The plan status.
        'app_uid': '', #: str: The app's uid.
        'plan_uid': '', #: str: The plan's uid.
        'plan_dict': {} #: dict: keys are the component names (the original name -- without uids), value is the respective CompDict.
    }
}

def create_pod_dict(host, event, pod_spec=None):
    pod_dict = copy.deepcopy(PodDict)

    pod_dict['hostname'] = host
    pod_dict['event'] = event
    
    if pod_spec:
        pod_dict['pod_spec'] = pod_spec
    
    return pod_dict

def create_msg(app_name, event, app_spec=None, status=None, \
               plan_uid=None, app_uid=None, comp_dict=None):
    if not event:
        logger.error('No event was set. Failed to create msg.')
        return

    agent_msg = copy.deepcopy(EventDict)
    agent_msg['event'] = event
    logger.info(f'create_msg event {event}')

    match event:
        case MessageEvents.APP_CREATED.value | MessageEvents.APP_UPDATED.value | MessageEvents.APP_DELETED.value:
            agent_msg["payload"] = {
                "name": app_name,
                "spec": app_spec,
                "app_uid": app_uid
            }

            if status:
                agent_msg["payload"]["status"] = status
            
            if comp_dict:
                agent_msg["payload"]["comp_dict"] = comp_dict

        case MessageEvents.PLAN_EXECUTED.value:
            agent_msg["payload"] = {
                "name": app_name,
                "spec": app_spec,
                "status": status,
                "app_uid": app_uid,
                "comp_dict": comp_dict
            }

            if plan_uid:
                agent_msg["payload"]["plan_uid"] = plan_uid

        case _:
            logger.error(f'create_msg unknown event {event}')
    
    return agent_msg

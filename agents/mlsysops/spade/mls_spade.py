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

import asyncio
import inspect
from queue import Queue
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.message import Message
from spade.template import Template

from ..logger_util import logger

try:
    from .behaviors.CheckInactiveClustersBehaviour import CheckInactiveClustersBehaviour
except Exception as e:
    logger.warning(f"Failed to import CheckInactiveClustersBehaviour: {e}")
    CheckInactiveClustersBehaviour = None

try:
    from .behaviors.Check_ml_deployment_Behaviour import Check_ml_deployment_Behaviour
except Exception as e:
    logger.warning(f"Failed to import Check_ml_deployment_Behaviour: {e}")
    Check_ml_deployment_Behaviour = None

try:
    from .behaviors.HBRecieverBehaviour import HBReceiverBehaviour
except Exception as e:
    logger.warning(f"Failed to import HBReceiverBehaviour: {e}")
    HBReceiverBehaviour = None

try:
    from .behaviors.ML_process_Behaviour import ML_process_Behaviour
except Exception as e:
    logger.warning(f"Failed to import ML_process_Behaviour: {e}")
    ML_process_Behaviour = None

try:
    from .behaviors.ManagementModeBehaviour import ManagementModeBehaviour
except Exception as e:
    logger.warning(f"Failed to import ManagementModeBehaviour: {e}")
    ManagementModeBehaviour = None

try:
    from .behaviors.FailoverBehaviour import FailoverBehavior
except Exception as e:
    logger.warning(f"Failed to import FailoverBehavior: {e}")
    FailoverBehavior = None

try:
    from .behaviors.ProcessBehaviour import ProcessBehaviour
except Exception as e:
    logger.warning(f"Failed to import ProcessBehaviour: {e}")
    ProcessBehaviour = None

try:
    from .behaviors.HeartbeatBehavior import HeartbeatBehaviour
except Exception as e:
    logger.warning(f"Failed to import HeartbeatBehaviour: {e}")
    HeartbeatBehaviour = None

try:
    from .behaviors.MessageReceivingBehavior import MessageReceivingBehavior
except Exception as e:
    logger.warning(f"Failed to import MessageReceivingBehavior: {e}")
    MessageReceivingBehavior = None

try:
    from .behaviors.MessageSendingBehavior import MessageSendingBehavior
except Exception as e:
    logger.warning(f"Failed to import MessageSendingBehavior: {e}")
    MessageSendingBehavior = None

try:
    from .behaviors.SubscribeBehavior import Subscribe
except Exception as e:
    logger.warning(f"Failed to import Subscribe: {e}")
    Subscribe = None

try:
    from .behaviors.APIPingBehaviour import APIPingBehaviour
except Exception as e:
    logger.warning(f"Failed to import APIPingBehaviour: {e}")
    APIPingBehaviour = None

try:
    from .behaviors.ManageSubscriptionBehaviour import ManageSubscriptionBehaviour
except Exception as e:
    logger.warning(f"Failed to import ManageSubscriptionBehaviour: {e}")
    ManageSubscriptionBehaviour = None
from ..data.state import MLSState
from mlsysops.spade.redis_mgt import RedisManager


class MLSSpade(Agent):

    def __init__(self, state: MLSState, message_queue: asyncio.Queue):
        super().__init__(state.configuration.n_jid, state.configuration.n_pass)

        self.is_subscribed = None
        self.cluster = state.configuration.cluster
        self.subscription_manager = state.configuration.c_jid
        self.snapshot_queue = Queue()
        self.message_queue = message_queue
        self.redis = RedisManager()

        if state.configuration.continuum_layer != "node":
            self.redis.connect()
        self.state = state
        self.behaviours_config = state.configuration.behaviours
        self.behaviour_classes = {}

        try:
            self.behaviour_classes["APIPingBehaviour"] = APIPingBehaviour
        except Exception as e:
            logger.warning(f"Failed to add APIPingBehaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["CheckInactiveClustersBehaviour"] = CheckInactiveClustersBehaviour
        except Exception as e:
            logger.warning(f"Failed to add CheckInactiveClustersBehaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["Check_ml_deployment_Behaviour"] = Check_ml_deployment_Behaviour
        except Exception as e:
            logger.warning(f"Failed to add Check_ml_deployment_Behaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["HBReceiverBehaviour"] = HBReceiverBehaviour
        except Exception as e:
            logger.warning(f"Failed to add HBReceiverBehaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["HeartbeatBehaviour"] = HeartbeatBehaviour
        except Exception as e:
            logger.warning(f"Failed to add HeartbeatBehaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["ML_process_Behaviour"] = ML_process_Behaviour
        except Exception as e:
            logger.warning(f"Failed to add ML_process_Behaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["ManagementModeBehaviour"] = ManagementModeBehaviour
        except Exception as e:
            logger.warning(f"Failed to add ManagementModeBehaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["ManageSubscriptionBehaviour"] = ManageSubscriptionBehaviour
        except Exception as e:
            logger.warning(f"Failed to add ManageSubscriptionBehaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["MessageReceivingBehavior"] = MessageReceivingBehavior
        except Exception as e:
            logger.warning(f"Failed to add MessageReceivingBehavior to behaviour_classes: {e}")

        try:
            self.behaviour_classes["MessageSendingBehavior"] = MessageSendingBehavior
        except Exception as e:
            logger.warning(f"Failed to add MessageSendingBehavior to behaviour_classes: {e}")

        try:
            self.behaviour_classes["ProcessBehaviour"] = ProcessBehaviour
        except Exception as e:
            logger.warning(f"Failed to add ProcessBehaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["FailoverBehaviour"] = FailoverBehavior
        except Exception as e:
            logger.warning(f"Failed to add FailoverBehaviour to behaviour_classes: {e}")

        try:
            self.behaviour_classes["Subscribe"] = Subscribe
        except Exception as e:
            logger.warning(f"Failed to add Subscribe to behaviour_classes: {e}")

    async def send_message(self, recipient: str, event: str, payload: dict):
        behavior = MessageSendingBehavior(recipient, event, payload)
        self.add_behaviour(behavior)

    async def new_agent_appeared(self, agent_jid):
        pass

    async def setup(self):
        self.is_subscribed = False
        logger.debug("MLSSpade agent setup")

        for behaviour_name, config in self.behaviours_config.items():
            try:
                if not config.get("enabled", False):
                    break

                behaviour_class = self.behaviour_classes.get(behaviour_name)
                if not behaviour_class:
                    logger.warning(f"No behavior class found for {behaviour_name}")
                    continue

                # Exclude the 'enabled' flag and get the rest of the parameters from the config
                config_params = {k: v for k, v in config.items() if k != "enabled"}

                try:
                    sig = inspect.signature(behaviour_class.__init__)
                except Exception as e:
                    logger.error(f"Cannot inspect __init__ for {behaviour_name}: {e}")
                    continue

                # The first parameter is 'self'; skip it.
                valid_params = list(sig.parameters.keys())[1:]
                # Filter config_params to include only valid constructor parameters
                filtered_params = {k: v for k, v in config_params.items() if k in valid_params}

                # Inject required parameters if they are missing
                if "redis_manager" in valid_params and "redis_manager" not in filtered_params:
                    filtered_params["redis_manager"] = self.redis

                if "message_queue" in valid_params and "message_queue" not in filtered_params:
                    filtered_params["message_queue"] = self.message_queue

                if "agent_to_subscribe" in valid_params and "agent_to_subscribe" not in filtered_params:
                    filtered_params["agent_to_subscribe"] = self.subscription_manager

                # Instantiate the behavior with the filtered (and possibly injected) parameters
                behaviour_instance = behaviour_class(**filtered_params)
                self.add_behaviour(behaviour_instance)
                logger.debug(f"Added behavior: {behaviour_name} with params {filtered_params}")
                break
            except Exception as e:
                logger.warning(f"Error instantiating {behaviour_name}: {e}")
                continue

        agent_exec_ins_behaviour = MessageReceivingBehavior(self.message_queue)
        self.add_behaviour(agent_exec_ins_behaviour)

        logger.debug("MLSSpade agent setup finished")




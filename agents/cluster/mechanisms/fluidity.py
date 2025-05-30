
import asyncio
import fluidity.controller as fluidity_controller
from mlsysops.logger_util import logger
from mlsysops import MessageEvents

queues = {"inbound": None, "outbound": None}



def initialize(inbound_queue=None, outbound_queue=None):
    print("Initializing fluidity mechanism")

    queues["inbound"] = inbound_queue
    queues["outbound"] = outbound_queue
    # Reverse the in- and out-, to make it more clear.
    asyncio.create_task(fluidity_controller.main(outbound_queue=inbound_queue,
                                                 inbound_queue=outbound_queue))


async def apply(plan):
    logger.debug(f"Applying fluidity plan {plan}")
    msg = {
        'event': MessageEvents.PLAN_SUBMITTED.value,
        'payload': plan
    }
    await queues['outbound'].put(msg)

async def send_message(msg):
    logger.debug(f"Sending message to fluidity {msg}")
    await queues['outbound'].put(msg)

def get_state():
    return {}

def get_options():
    return {}
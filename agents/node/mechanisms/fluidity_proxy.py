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


from mlsysops.events import MessageEvents
import asyncio

queues = {"inbound": None, "outbound": None}
state = None
node_name = None
async def fluidity_proxy_loop():
    global state
    global queues
    while True:
        message = await queues['inbound'].get()

        event = message['event']
        payload = message['payload']
        match (event):
            case MessageEvents.MESSAGE_TO_FLUIDITY_PROXY.value:
                fluidity_internal_payload = payload.get("payload", {})
                fluidity_internal_event = payload.get("event", None)
                match fluidity_internal_event:
                    case MessageEvents.FLUIDITY_INTERNAL_PLAN_UPDATE.value:
                        await queues['outbound'].put(fluidity_internal_payload)
                    case MessageEvents.FLUIDITY_INTERNAL_STATE_UPDATE.value:
                        # update internal state
                        state = payload
            case "NETWORK_REDIRECT":
                continue # TODO
            case _:
                print("Unknown event in fluidity proxy")
        pass

    return False # async

def initialize(inbound_queue=None, outbound_queue=None, agent_state=None):
    global node_name

    queues["inbound"] = outbound_queue
    queues["outbound"] = inbound_queue

    node_name = agent_state.configuration.node

    asyncio.create_task(fluidity_proxy_loop())

async def apply(plan):
    print("--------------------------Applying fluidity plan", plan)
    global node_name
    # This mechanism uses the messaging interface to send to cluster fluidity
    await queues['outbound'].put({
        "event": MessageEvents.MESSAGE_TO_FLUIDITY.value,
        "payload": {
            "event": MessageEvents.FLUIDITY_INTERNAL_PLAN_SUBMITTED.value,
            "payload": {
                "event": MessageEvents.PLAN_SUBMITTED.value,
                "payload": plan
            },
            "node": node_name
        }
    })


def get_state():
    global state
    return state


def get_options():
    pass
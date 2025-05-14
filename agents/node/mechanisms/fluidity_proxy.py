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


async def fluidity_proxy_loop():

    while True:
        message = await queues['inbound'].get()

        event = message['event']
        payload = message['payload']

        match (event):
            case "NETWORK_REDIRECT":
                continue # TODO
            case _:
                print("Unknown event in fluidity proxy")
        pass

def initialize(inbound_queue=None, outbound_queue=None):
    print("Initializing fluidity proxy mechanism")

    queues["inbound"] = outbound_queue
    queues["outbound"] = inbound_queue

    asyncio.create_task(fluidity_proxy_loop())

async def apply(plan):


    print("--------------------------Applying fluidity plan", plan)

    # This mechanism uses the messaging interface to send to cluster fluidity
    await queues['outbound'].put({
        "event": MessageEvents.MESSAGE_TO_FLUIDITY.value,
        "payload": plan
    })
    pass


def get_state():
    pass


def get_options():
    pass
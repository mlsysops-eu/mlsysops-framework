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
import multiprocessing
import random
import spade
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour, OneShotBehaviour
from spade.template import Template
from spade.message import Message

from datetime import datetime, timedelta
import subprocess
import json
import uuid

import mlsysops
from Cluster_agent import config
from mlsysops import events


class ClusterAgent(Agent):

    def __init__(self, jid: str, password: str,c_jid: str, message_queue: asyncio.Queue):
        super().__init__(jid, password)
        print("INIT")
        self.check_process_behaviour = None
        self.launch_fluidity_behaviour = None
        self.analyze_behaviour = None
        self.ping_receiver_behaviour = None
        self.check_inactive_slaves_behaviour = None
        self.ping_behaviour = None
        self.deploy_behaviour = None
        self.monitor_behaviour = None
        self.lock = None
        self.subscribers = None
        self.timeout = timedelta(seconds=60)
        self.inform_config = None
        self.message_queue = message_queue
        print(message_queue)

    class CheckProcessBehaviour(CyclicBehaviour):
        async def run(self):
            if self.agent.process.poll() is None:
                print("Process is still running")
            else:
                print("Process has terminated")
                self.kill()  # Stop the cyclic behaviour if the process is terminated
            #await asyncio.sleep(5)  # Check every 5 seconds
            output = self.agent.process.stdout.readline()
            if output:
                print(output.strip())

    class ManageSubscriptionBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive()  # Wait for a subscription message
            if msg:
                print(msg.thread)
                sender = str(msg._sender).split("/")[0]
                resp = Message(to=sender)  # Instantiate the message
                resp.set_metadata("performative", "subscription")
                resp.thread = msg.thread
                async with self.agent.lock:
                    if sender not in self.agent.subscribers:
                        self.agent.subscribers[sender] = True  # Assume true means available

                        resp.body = "Subscription succeed "  # Set the message content
                        await self.send(resp)
                    else:
                        print("JID on list already subscribed")
                        resp.body = "Agent already subscribed "  # Set the message content
                        await self.send(resp)

    class PingBehaviour(CyclicBehaviour):
        """
                A behavior that receives messages and sends responses.
                This is used to do the heartbeat.
         """

        async def run(self):
            """Continuously receive and respond to messages in a cyclic manner."""
            print("PingBehav running")

            # wait for a message for 10 seconds
            msg = await self.receive(timeout=10)
            if msg:
                print(str(msg._sender).split("/")[0])
                print(msg.to)
                print("Ping received with content: {}".format(msg.body))

                # Create a response message
                resp = Message(to=str(msg._sender).split("/")[0])  # Replace with the actual recipient JID
                resp.set_metadata("performative", "ping")  # Set the "inform" FIPA performative
                resp.body = "Response From " + str(msg.to)  # Set the message content
                print(resp.body)
                # Send the response message
                await self.send(resp)
                print("Callback message sent!\n")
            else:
                print("Did not received any message after 10 seconds")

                await asyncio.sleep(10)

    class PingReceiverBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=2)  # Wait for a message for 10 seconds
            if msg:
                slave_id = str(msg.sender).split("/")[0]
                now = datetime.now()
                self.agent.subscribers[slave_id] = now
                print(f"Received ping from {slave_id} at {now}.")

    class CheckInactiveSlavesBehaviour(PeriodicBehaviour):
        async def run(self):
            # Get the current time
            now = datetime.now()

            # Initialize an empty list to hold inactive subscribers
            inactive_slaves = []

            # Iterate through the subscribers dictionary
            for slave_id, last_ping in self.agent.subscribers.items():
                # Check if last_ping is a datetime object and if the time since last ping is greater than the timeout
                if isinstance(last_ping, datetime) and (
                        now - last_ping) > self.agent.timeout:  # time out is defined at the cluster agent
                    # Add the slave_id to the inactive list
                    inactive_slaves.append(slave_id)

            for slave_id in inactive_slaves:
                print("_____________________________________________INACTIVE NODE______________________")
                print(f"Agent {slave_id} is inactive.")
                print("_____________________________________________INACTIVE NODE______________________")

    class ApplicationMonitor(PeriodicBehaviour):
        async def run(self):
            msg = Message(to="receiver_agent@server")  # Recipient JID
            msg.set_metadata("performative", "inform")  # Standard performative
            msg.set_metadata("event", mlsysops.events.MessageEvents.COMPONENT_PLACED.value)  # Custom metadata field
            msg.thread = str(uuid.uuid4())

            payload = {
                "application_id" : "test",
                "component_spec" : {"target": 1},
                "pod_spec" : {"image": 1}
            }

            serialized_payload = json.dumps(payload)

            msg.body = serialized_payload

            self.send(msg)

    class MessageReceivingBehavior(CyclicBehaviour):

        def __init__(self,message_queue: asyncio.Queue):
            super().__init__()
            self.message_queue = message_queue

        async def run(self):

            print("Receiving message Cluster Behaviour")
            msg = await self.receive(timeout=10)  # wait for a message for 10 seconds
            if msg:
                sender = str(msg._sender).split("/")[0]

                # Decode message
                performative = msg.get_metadata("performative")
                event = msg.get_metadata("event")
                thread = msg.thread

                resp = Message(to=sender)
                resp.thread = msg.thread

                match (performative, event):
                    case ("request", mlsysops.events.MessageEvents.RECONFIGURATION.value):
                        # Inform fluidity
                        print("Application Component Placed")
                        # Decode payload
                        payload = {
                            "event": event,
                            "payload": json.loads(msg.body)
                        }
                        # inform agent for receiving
                        await self.message_queue.put(payload)

                # print("Command to be executed ------------------------------------------------------------")
                # try:
                #     resp.set_metadata("performative", "inform-done")
                #     resp.body = "done "
                #     test_fucntion()
                #     print("done")
                #
                # except:
                #     resp.set_metadata("performative", "failure")
                #     resp.body = "failure"
                #     print("error in execution")
                # print("----------------------------------------------------------------")
                # await self.send(resp)

            else:
                print("Did not received any message after 10 seconds")

    class SendSingleMessageBehavior(OneShotBehaviour):
        """
        Handles sending a single message using a OneShotBehaviour.

        This class is designed to encapsulate the behavior for sending a single
        message to a specified recipient. It allows setting the message's metadata,
        like performative and event, and includes the message payload in its body.
        This behavior is executed asynchronously.

        Attributes:
            event (str): A string specifying the event type or identifier to be
                included in the message metadata.
            payload (str): The content of the message to be sent.
            node (str): The identifier of the recipient node for this message.
                This will be combined with a domain to form the recipient's JID.
        """
        def __init__(self,event, payload, node):
            super().__init__()
            self.event = event
            self.payload = payload
            self.node = node

        async def run(self):
            # Create a response message
            print(f"Sending message to {self.node}")
            msg = Message(to=f"{self.node}@{config.domain}" ) # TODO Replace with the actual recipient JID
            msg.set_metadata("performative", "informative")  # Set the "inform" FIPA performative
            msg.set_metadata("event",self.event)
            msg.body = self.payload # Set the message content

            # Send the response message
            resp = await self.send(msg)
            if resp == None:
                print("SendSingleMessageBehavior: No response from agent: "+self.node)
            else:
                print("SendSingleMessageBehavior: Sent msg to spade agent. Caught resp "+resp)

    async def send_message_to_node(self,event, payload, node):
        """
        Asynchronously sends a message to a specified node by adding a behavior. This method
        triggers the execution of a behavior responsible for sending a single message to the
        designated node associated with the given event and payload.

        Parameters:
            event: str
                The event identifier associated with the message.
            PROBABLY MUST ME A STRING
            payload: Any
                The payload or data to be sent as part of the message.
            node: str
                The identifier of the destination node to which the message will be sent.
        """
        self.add_behaviour(self.SendSingleMessageBehavior(event, payload, node))

    async def setup(self):
        print("Starting cluster agent ... ")

        self.subscribers = {}
        self.lock = asyncio.Lock()

        # ---------------Manage subscription-----------------------

        sub_template = Template()
        sub_template.set_metadata("performative", "subscribe")
        agent_sub = self.ManageSubscriptionBehaviour()
        self.add_behaviour(agent_sub, sub_template)

        ping_template = Template()
        ping_template.set_metadata("performative", "ping")
        self.ping_behaviour = self.PingBehaviour()
        self.add_behaviour(self.ping_behaviour, ping_template)

        self.ping_receiver_behaviour = self.PingReceiverBehaviour()
        self.add_behaviour(self.ping_receiver_behaviour)

        self.check_inactive_slaves_behaviour = self.CheckInactiveSlavesBehaviour(period=5)
        self.add_behaviour(self.check_inactive_slaves_behaviour)

        self.agent_exec_ins_behaviour = self.MessageReceivingBehavior(self.message_queue)
        self.add_behaviour(self.agent_exec_ins_behaviour)
        # agent_exec_ins_behaviour = self.MessageReceivingBehavior()
        # self.add_behaviour(agent_exec_ins_behaviour)
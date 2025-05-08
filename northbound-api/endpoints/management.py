import asyncio
from fastapi import FastAPI, APIRouter, HTTPException
import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message
from spade.template import Template
from redis_setup import redis_mgt as rm
import time

app = FastAPI()
router = APIRouter()

r = rm.RedisManager()
r.connect()


class NBAgent(Agent):

    def __init__(self, jid: str, password: str):
        super().__init__(jid, password)
        self.ping_behaviour = None

    class PingBehaviour(OneShotBehaviour):
        """ A behavior that sends a ping message to a specific recipient and waits for a response. """

        async def run(self):
            print("PingBehaviour running...")
            recipient_jid = "continuum@karmada.mlsysops.eu"
            time.sleep(2)

            # Create a ping message
            msg = Message(to=recipient_jid)
            msg.set_metadata("performative", "ping")
            msg.body = "Ping from " + str(self.agent.jid)

            print(f"Sending ping to {recipient_jid}")
            await self.send(msg)

            # Wait for response for 5 seconds
            response = await self.receive(timeout=10)
            if response:
                print(f"Received response: {response.body}")
                print("Agent Alive")
                return {"status": "alive", "response": response.body}
            else:
                print("Did not receive a response. Agent Error.")
                return {"status": "error", "message": "No response received"}

    async def setup(self):
        print("Starting NBAPI agent...")
        redis_manager = rm.RedisManager()
        redis_manager.connect()

        self.ping_behaviour = self.PingBehaviour()
        self.add_behaviour(self.ping_behaviour)


class MLAgent(Agent):

    def __init__(self, jid: str, password: str):
        super().__init__(jid, password)
        self.manage_behaviour = None

    class ManageModeBehaviour(OneShotBehaviour):
        """
        A behavior that sends a message with the new management mode (0 or 1) to recipients.
        """

        def __init__(self, redis_manager, mode):
            super().__init__()
            self.r = redis_manager
            self.mode = mode  # Store the mode value (0 or 1)

        async def run(self):
            print(f"ManageModeBehaviour running with mode {self.mode}...")

            recipient_jids = self.r.get_keys("system_agents")
            recipient_jids.append("continuum@karmada.mlsysops.eu")
            for recipient_jid in recipient_jids:
                msg = Message(to=recipient_jid)
                msg.set_metadata("performative", "ch_mode")
                msg.body = f"Change management mode to: {self.mode}"  # Send mode in the message
                print(f"Sending mode {self.mode} to {recipient_jid}")
                await self.send(msg)

    async def setup(self):
        print("Starting ML_client agent...")


@router.get("/ping", tags=["Management"])
async def ping():
    nbapi_agent = NBAgent("nbapi@karmada.mlsysops.eu", "1234")
    await nbapi_agent.start(auto_register=True)
    result = await nbapi_agent.ping_behaviour.run()
    await nbapi_agent.stop()

    if result["status"] == "alive":
        return {"status": "success", "message": "Agent Alive", "response": result["response"]}
    else:
        raise HTTPException(status_code=500, detail={"status": "error", "message": result["message"]})


@router.put("/mode/{mode}", tags=["Management"])
async def set_mode(mode: int):
    """
    Accepts mode value (0 or 1) and sends it to system agents.
    """
    if mode not in [0, 1]:
        raise HTTPException(status_code=400, detail="Mode must be 0 or 1")

    ml_client_agent = MLAgent("nbapi@karmada.mlsysops.eu", "1234")
    await ml_client_agent.start(auto_register=True)

    # Create and add behavior with the mode value
    manage_behaviour = ml_client_agent.ManageModeBehaviour(r, mode)
    ml_client_agent.add_behaviour(manage_behaviour)

    await manage_behaviour.run()
    await ml_client_agent.stop()

    return {"status": "success", "message": f"Mode {mode} sent to system agents"}

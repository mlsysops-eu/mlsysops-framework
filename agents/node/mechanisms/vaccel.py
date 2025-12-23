import os
import asyncio
from typing import Any, Dict

import requests

from mlsysops.events import MessageEvents
from mlsysops.data.task_log  import Status

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://10.64.82.70:5000")

inbound_queue = None
self_outbound_queue = None

def initialize(inbound_queue, outbound_queue, agent_state=None):
    """
    Optional initialization hook for the agent.

    Currently a no-op, but you can wire inbound/outbound queues or agent_state
    here if needed later.
    """
    global self_outbound_queue
    # Placeholder for future use
    print(f"ini {outbound_queue}")
    self_outbound_queue = outbound_queue
    return


async def apply(value: Dict[str, Any]) -> bool:
    """
    Apply a backend configuration by calling the /set-backend endpoint.

    Expected `value` structure:
        {
            "backend": "<backend-name>",        # e.g. "stock", "vaccel-local", "vaccel-bf"
            "remote_address": "<host:port>"    # optional, for remote backends
        }
    """
    global self_outbound_queue
    backend_name = value.get("backend")
    remote_address = value.get("remote_address", None)

    if not backend_name:
        print("apply() called without 'backend' in value")
        return False

    payload = {
        "name": backend_name,
        "remote_address": remote_address,
    }

    url = f"{BACKEND_API_URL}/set-backend"

    def _post():
        return requests.post(url, json=payload, timeout=5)

    try:
        response = await asyncio.to_thread(_post)
        if not response.ok:
            print(f"Failed to set backend: {response.status_code} {response.text}")
            await self_outbound_queue.put({
                "event": MessageEvents.PLAN_EXECUTED.value,
                "payload": {
                    "plan_uid": value["plan_uid"],
                    "status": Status.FAILED.value
                }
            })
            return False
        print(f"Successfully set backend to {backend_name} {response.json()}")
        await self_outbound_queue.put({
            "event": MessageEvents.PLAN_EXECUTED.value,
            "payload": {
                "plan_uid": value["plan_uid"],
                "status": Status.COMPLETED.value
            }
        })
        return True
    except Exception as e:
        print(f"Error calling {url}: {e}")
        return False


def get_options() -> Dict[str, Any]:
    """
    Fetch available backend options from /get-backends endpoint.

    Returns the JSON response on success, or {} on failure.
    """
    url = f"{BACKEND_API_URL}/get-backends"
    try:
        response = requests.get(url, timeout=5)
        if not response.ok:
            print(f"Failed to fetch backends: {response.status_code} {response.text}")
            return {}
        return response.json()
    except Exception as e:
        print(f"Error calling {url}: {e}")
        return {}


def get_state() -> Dict[str, Any]:
    """
    Return current state for this agent by querying the active backend
    from /get-active-backend.

    Returns the JSON response on success, or {} on failure.
    """
    url = f"{BACKEND_API_URL}/get-active-backend"
    try:
        response = requests.get(url, timeout=5)
        if not response.ok:
            print(f"Failed to fetch active backend: {response.status_code} {response.text}")
            return {}
        return response.json()
    except Exception as e:
        print(f"Error calling {url}: {e}")
        return {}
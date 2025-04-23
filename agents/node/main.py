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

from __future__ import print_function

import asyncio
import os

from dotenv import load_dotenv

from mlsysops.logger_util import logger
from node_agent import MLSNodeAgent

# Path to your .env file
dotenv_path = '.env'

# Check if the .env file exists
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)  # Load the .env file into environment variables
    logger.debug(f".env file found and loaded from: {dotenv_path}")
else:
    logger.debug(f"No .env file found at: {dotenv_path}")


async def shutdown(signal_name, agent, all_tasks):
    """
    Gracefully shuts down the asyncio event loop.

    Args:
        signal_name (str): The name of the received signal (e.g., SIGTERM, SIGINT).
        agent (MLSClusterAgent): The agent instance to be stopped or cleaned.
        all_tasks (list): List of running asyncio tasks to cancel.
    """
    logger.info(f"Received {signal_name}. Shutting down gracefully...")

    # Gracefully stop the MLSClusterAgent
    try:
        await agent.stop()  # Assuming `stop` is a method for cleanup in your agent class
        logger.debug("Agent stopped successfully.")
    except Exception as e:
        logger.error(f"Error while stopping the agent: {e}")

    # Cancel all running tasks
    for task in all_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.debug(f"Task {task} cancelled successfully.")
        except Exception as e:
            logger.error(f"Error while cancelling the task {task}: {e}")

    logger.info("Shutdown complete. Exiting process.")



async def main():
    """
    Entry point for the node agent program.
    This function initializes and runs the MLS Node Agent.
    """
    global main_task

    # Instantiate the MLSAgent class
    agent = MLSNodeAgent()

    try:
        # Run the MLSAgent's main process (update with the actual method name)
        agent_task = asyncio.create_task(agent.run())
        main_task = agent_task

        await asyncio.gather(agent_task)

    except asyncio.CancelledError:
        logger.info("Agent stoped. Performing cleanup...")
        if agent:
            await agent.stop()  # Stop the agent during cleanup
    except Exception as e:
        logger.error(f"An error occurred in the main task: {e}")


if __name__ == "__main__":
    asyncio.run(main())

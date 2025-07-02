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
import os
from dotenv import load_dotenv
import asyncio
from MLSClusterAgent import MLSClusterAgent
from mlsysops.logger_util import logger

# Path to your .env file
dotenv_path = '.env'

# Check if the .env file exists
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)  # Load the .env file into environment variables
    logger.debug(f".env file found and loaded from: {dotenv_path}")
else:
    logger.debug(f"No .env file found at: {dotenv_path}")

async def main():
    """
    Entry point for the asyncio program.
    This function initializes and runs the MLSAgent.
    """
    global main_task

    # Instantiate the MLSAgent class
    agent = MLSClusterAgent()
    try:
        # Run the MLSAgent's main process (update with the actual method name)
        agent_task = asyncio.create_task(agent.run())
        main_task = agent_task

        await asyncio.gather(agent_task)

    except asyncio.CancelledError:
        logger.info("Agent stoped. Performing cleanup...")
        if agent:
            await agent.stop()  # Stop the agent during cleanup

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt as e:
        logger.info("MLSAgent stopped.")

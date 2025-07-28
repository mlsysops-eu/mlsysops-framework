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
from MLSContinuumAgent import MLSContinuumAgent

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
    Entry point for the node agent program.
    This function initializes and runs the MLS Node Agent.
    """
    try:
        # Instantiate the MLSAgent class
        agent = MLSContinuumAgent()

        # Run the MLSAgent's main process (update with the actual method name)
        agent_task = asyncio.create_task(agent.run())

        await asyncio.gather(agent_task)

    except Exception as e:
        logger.error(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())

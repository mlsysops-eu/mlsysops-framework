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

import logging
import os


def setup_logger(logger_name: str, log_file: str) -> logging.Logger:
    """
    Sets up and configures a logger.

    :param logger_name: Name of the logger.
    :param log_file: File path to save the logs.
    :return: Configured logger instance.
    """
    # Get log level from environment variables
    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    if log_level not in valid_levels:
        raise ValueError(f"Invalid log level: {log_level}. Valid levels: {valid_levels}")

    # Get or create the logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # Clear previous handlers if they exist
    if not logger.hasHandlers():
        # Create file handler and console handler
        file_handler = logging.FileHandler(log_file)
        console_handler = logging.StreamHandler()

        # Use the same log level for both handlers
        file_handler.setLevel(log_level)
        console_handler.setLevel(log_level)

        # Setup formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s [%(filename)s] %(message)s"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # if os.getenv("LOKI_LOG_ENABLED", "true"):
        #     import mlstelemetry
        #

    return logger


# Initialize the logger as a global instance
logger = setup_logger("MLSAgent", "agent.log")
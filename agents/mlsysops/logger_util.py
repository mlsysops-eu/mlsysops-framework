#  Copyright (c) 2025. MLSysOps Consortium
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import logging
import os
from functools import partial, partialmethod

# Define ANSI escape codes for colors
LOG_COLORS = {
    "DEBUG": "\033[93m",   # Gray
    "INFO": "\033[92m",    # Green
    "WARNING": "\033[93m", # Orange (actually yellow in ANSI but close enough for terminal)
    "ERROR": "\033[91m",   # Red
    "CRITICAL": "\033[95m", # Bright Magenta
    "TEST": "\033[93m"
}
RESET_COLOR = "\033[0m"

def add_logging_level(level_name, level_num, method_name=None):
    """
    Add a new logging level to the `logging` module and Logger class.

    :param level_name: name of the new level (e.g., "TRACE")
    :param level_num: integer value (eg, logging.DEBUG - 5)
    :param method_name: optional function name (defaults to level_name.lower())
    """
    if method_name is None:
        method_name = level_name.lower()

    # Avoid conflicts
    if hasattr(logging, level_name):
        raise AttributeError(f"{level_name} already exists in logging module")
    if hasattr(logging, method_name):
        raise AttributeError(f"{method_name} already exists in logging module")
    if hasattr(logging.getLoggerClass(), method_name):
        raise AttributeError(f"{method_name} already exists in Logger class")

    # Register the new level
    logging.addLevelName(level_num, level_name)
    setattr(logging, level_name, level_num)

    # Add method to Logger class
    setattr(logging.getLoggerClass(), method_name,
            partialmethod(logging.getLoggerClass().log, level_num))

    # Also add top-level function, e.g., logging.test(...)
    def root_level_method(msg, *args, **kwargs):
        logging.log(level_num, msg, *args, **kwargs)
    setattr(logging, method_name, root_level_method)

class CustomFormatter(logging.Formatter):
    """
    Custom logging formatter to dynamically include the caller's parent directory and filename.
    Optionally applies colors to log levels for the console output.
    """
    def __init__(self, fmt, use_colors: bool = False):
        """
        Initialize the formatter with optional color support.
        
        :param fmt: The log format string.
        :param use_colors: Whether to apply colors to the logs.
        """
        super().__init__(fmt)
        self.use_colors = use_colors

    def format(self, record):
        # Dynamically resolve `parentdir/filename` where the log was called
        file_path = os.path.abspath(record.pathname)
        parent_dir = os.path.basename(os.path.dirname(file_path))
        record.filepath_display = f"{parent_dir}/{os.path.basename(file_path)}"

        if self.use_colors:
            # Add colors to log level and message only for console output
            log_color = LOG_COLORS.get(record.levelname.strip(), RESET_COLOR)
            record.levelname = f"{log_color}{record.levelname}{RESET_COLOR}"
            record.msg = f"{log_color}{record.msg}{RESET_COLOR}"
        return super().format(record)


def setup_logger(logger_name: str, log_file: str) -> logging.Logger:
    """
    Sets up and configures a logger.

    :param logger_name: Name of the logger.
    :param log_file: File path to save the logs.
    :return: Configured logger instance.
    """

    add_logging_level('TEST', logging.CRITICAL + 5)

    # Get log level from environment variables
    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "TEST"]

    if log_level not in valid_levels:
        raise ValueError(f"Invalid log level: {log_level}. Valid levels: {valid_levels}")

    # Get or create the logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # Clear previous handlers if they exist
    if not logger.hasHandlers():
        # Create file handler and console handler
        file_handler = logging.FileHandler(log_file, mode="w")
        console_handler = logging.StreamHandler()

        # Use the same log level for both handlers
        file_handler.setLevel(log_level)
        console_handler.setLevel(log_level)

        # Configure formatters: colored for console, plain for file
        console_formatter = CustomFormatter(
            "%(asctime)s - %(levelname)s [%(filepath_display)s] %(message)s",
            use_colors=True  # Enable colors for console
        )
        file_formatter = CustomFormatter(
            "%(asctime)s - %(levelname)s %(lineno)d [%(filepath_display)s] %(message)s",
            use_colors=False  # Disable colors for file logs
        )
        console_handler.setFormatter(console_formatter)
        file_handler.setFormatter(file_formatter)

        # Add handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


# Initialize the logger as a global instance
logger = setup_logger("MLSAgent", os.getenv("MLS_AGENT_LOG_PATH","agent.log"))
import os
import threading
from subprocess import Popen, PIPE
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from agents.mlsysops.logger_util import logger
import re
import json
import pytest


# Paths relative to PROJECT_DIR
AGENT_LOG_PATH = "agent.log"
AGENT_MAIN_PATH = "../../cluster/main.py"

EXPECTED_LOG_MARKER = "fluidity.py] |3|"

# Set environment variables for the test
ENV_VARS = {
    "KUBECONFIG": "/home/patras/agents/continuum/kubeconfigs/ubiwdev.kubeconfig",
    "NODE_NAME": "mls-ubiw-1",
    "CLUSTER_NAME": "mls-ubiw-1",
    "EJABBERD_DOMAIN": "karmada.mlsysops.eu",
    "NODE_PASSWORD": "1234",
    "MLSYSOPS_INSTALL_PATH": os.path.abspath("."),
    "MLS_OTEL_MIMIR_EXPORT_ENDPOINT": "http://10.64.82.70:9009/api/v1/push",
    "MLS_OTEL_LOKI_EXPORT_ENDPOINT": "http://10.64.82.70:3100/loki/api/v1/push",
    "MLS_OTEL_NODE_EXPORTER_FLAGS": "os,cpu",
    "MLS_OTEL_HIGHER_EXPORT": "ON",
    "LOCAL_OTEL_ENDPOINT": "http://172.25.27.226:9999/metrics",
    "LOG_LEVEL": "TEST",
    "PYTHONPATH": "/home/patras/agents:/home/patras/agents/cluster/fluidity"
}


class LogEventHandler(FileSystemEventHandler):
    """Handles agent.log file updates and triggers on marker detection."""

    def __init__(self, condition_event):
        self.condition_event = condition_event

    def on_modified(self, event):
        """Triggers when the log file is modified and checks for the marker."""
        global EXPECTED_LOG_MARKER
        if event.src_path.endswith("agent.log"):  # Ensure this is the correct log file
            with open(AGENT_LOG_PATH, "r") as logfile:
                logs = logfile.readlines()
                for line in logs:
                    if EXPECTED_LOG_MARKER in line:  # Check for the marker
                        self.condition_event.set()


def run_agent():
    """
    Runs the cluster/main.py script as a subprocess and ensures the agent starts.
    Captures stdout/stderr and writes them to both test.log and the console for debugging.
    """
    logger.info("Starting agent process...")
    env = os.environ.copy()
    env.update(ENV_VARS)

    # Start the agent process and capture stdout/stderr
    process = Popen(
        ["python3", AGENT_MAIN_PATH],
        env=env,
        stdout=PIPE,
        stderr=PIPE,
        text=True  # Text mode for easier string handling
    )
    return process


def parse_test_logs():
    """
    Parses the 'agent.log' file, processes log lines with "TEST" messages, 
    and builds a dictionary where each key is a test stage (path_filename) 
    with nested test-case data.

    The function ensures parsed data retains consistent `planuid` across stages, if present.
    The parsed result is written to a JSON file for debugging.

    Returns:
        dict: The nested dictionary structure parsed from log messages.
    """
    log_file_path = "agent.log"  # Path to the log file
    output_file_path = "parsed_test_logs.json"  # Output file for the parsed results

    # Update regex to split on <path>/<filename>.py and convert stage to path_filename
    log_pattern = re.compile(
        r"TEST\s\d+\s+\[(?P<stage>[\w/]+\.py)\]\s+\|(?P<test_number>\d+)\|\s+(?P<message>.+)"
    )

    parsed_logs = {}  # Dictionary to store the parsed results
    consistent_planuuid = None  # To ensure all stages use the same planuid

    logger.info("Parsing agent.log for TEST messages...")
    try:
        with open(log_file_path, "r") as logfile:
            logs = logfile.readlines()

        for line in logs:
            if "TEST" in line:
                match = log_pattern.search(line)

                if match:
                    # Extract <path>/<filename>.py as the stage and convert it
                    full_path = match.group("stage")  # e.g., "tasks/plan.py"
                    path_filename = full_path.replace("/", "_")  # Convert to "tasks_plan.py"

                    test_number = int(match.group("test_number"))  # Extracted test number as an integer
                    message = match.group("message")  # Remaining key-value pairs in the message

                    # Parse the key-value information in the message
                    message_data = {}
                    if message:
                        for pair in message.split():
                            if ":" in pair:
                                key, value = pair.split(":", 1)
                                key = key.strip()
                                value = value.strip()

                                # Enforce consistent planuid
                                if key == "planuid":
                                    if consistent_planuuid is None:
                                        consistent_planuuid = value
                                    elif value != consistent_planuuid:
                                        raise ValueError(
                                            f"Inconsistent planuid detected: "
                                            f"Found {value}, expected {consistent_planuuid}"
                                        )
                                    value = consistent_planuuid

                                message_data[key] = value

                    # Initialize the dictionary for the stage if not already present
                    if path_filename not in parsed_logs:
                        parsed_logs[path_filename] = {}

                    # Add the test_number and its nested data
                    parsed_logs[path_filename][test_number] = message_data

        # Write the resulting parsed_logs dictionary to a file as JSON
        logger.info(f"Writing parsed log data to {output_file_path}...")
        with open(output_file_path, "w") as outfile:
            json.dump(parsed_logs, outfile, indent=4)

        logger.info("Log parsing completed. Parsed data written to JSON.")
        return parsed_logs

    except FileNotFoundError:
        logger.error(f"Error: Log file {log_file_path} not found.")
    except Exception as e:
        logger.error(f"An error occurred while processing the logs: {e}")

def rename_file(old_filename, new_filename):
    try:
        # Rename the file
        os.rename(old_filename, new_filename)
        logger.info(f"File renamed from {old_filename} to {new_filename}.")
    except FileNotFoundError:
        logger.error(f"Error: {old_filename} not found.")
    except PermissionError:
        logger.error("Error: Permission denied.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

def assert_payloads(subtests, expected_logs, parsed_logs):
    # Step 3: Validate each stage using subtests
    for stage, expected_cases in expected_logs.items():
        with subtests.test(stage=stage):  # Create a subtest for each stage
            assert stage in parsed_logs, f"Missing stage: {stage} in parsed logs"
            for test_number, expected_data in expected_cases.items():
                with subtests.test(stage=stage, test_number=test_number):  # Subtest for each test in a stage
                    assert test_number in parsed_logs[stage], (
                        f"Missing test number {test_number} in stage {stage}"
                    )
                    for key, expected_value in expected_data.items():
                        actual_value = parsed_logs[stage][test_number].get(key)
                        assert actual_value == expected_value, (
                            f"{stage} > Test {test_number} > {key}: Expected {expected_value}, got {actual_value}"
                        )

    # Step 4: Ensure all `planuid` values are consistent across all stages
    all_planuids = {
        details["planuid"]
        for stage, tests in parsed_logs.items()
        for details in tests.values()
        if "planuid" in details
    }
    if all_planuids:
        with subtests.test("planuid_consistency"):
            assert len(all_planuids) == 1, (
                f"Inconsistent `planuid` values found across stages: {all_planuids}"
            )

    logger.info("All parsed logs match expected statuses and structure!")

@pytest.mark.timeout(40)  # Fail the test if it exceeds 40 seconds
def test_cluster_relocate_plan(subtests):
    """
    Test the execution flow of a cluster plan lifecycle and validate its status updates across
    different stages. This function sets up a test environment, monitors log outputs, and evaluates
    expected results for various lifecycle stages of a cluster execution plan.

    Parameters:
        subtests (SubTests): A SubTests instance for managing multiple subtest contexts within
                             a single test function.
    """
    logger.info("Setting up environment variables...")
    for key, value in ENV_VARS.items():
        os.environ[key] = value

    stop_event = threading.Event()
    observer = Observer()
    event_handler = LogEventHandler(stop_event)
    observer.schedule(event_handler, path=os.path.abspath("./"), recursive=False)

    # Activate a policy, by renaming it
    old_filename = f"policies/_policy-relocateComponents.py"
    new_filename = f"policies/policy-relocateComponents.py"
    rename_file(old_filename,new_filename)

    # Runt agent
    agent_process = run_agent()

    try:
        observer.start()
        logger.debug(f"Watching marker in {AGENT_LOG_PATH}: {EXPECTED_LOG_MARKER}")
        if not stop_event.wait(timeout=30):
            logger.debug("Timeout: Marker not found in logs.")
        else:
            logger.debug(f"Marker found: {EXPECTED_LOG_MARKER}")
        agent_process.terminate()

    finally:
        observer.stop()
        observer.join()
        if agent_process.poll() is None:
            agent_process.terminate()



    # Restore and deactivate a policy, by renaming it
    old_filename = f"policies/policy-relocateComponents.py"
    new_filename = f"policies/_policy-relocateComponents.py"
    rename_file(old_filename,new_filename)

    # Step 1: Parse logs
    parsed_logs = parse_test_logs()


    # Step 2: Define the expected structure with updated stage names
    expected_logs = {
        "tasks_analyze.py": {
            2: {"status": "True"}
        },
        "tasks_plan.py": {
            1: {"policy": "relocateComponents"}
        },
        "mlsysops_scheduler.py": {
            1: {"status": "Scheduled"}
        },
        "mechanisms_fluidity.py": {
            1: {"status": "True"},
            2: {"status": "MLSClusterAgent"},
            3: {"status": "Success"}
        },
        "tasks_execute.py": {
            1: {"status": "Pending"}
        },
        "fluidity_controller.py": {
            1: {"status": "True"},
            2: {"status": "Completed"}
        },
        "cluster_MLSClusterAgent.py": {
            1: {"status": "Completed"}
        }
    }

    assert_payloads(subtests, expected_logs=expected_logs,parsed_logs=parsed_logs)


# @pytest.mark.timeout(40)  # Fail the test if it exceeds 40 seconds
# def test_cluster_static_placement_plan(subtests):
#     """
#     Test the execution flow of a cluster plan lifecycle and validate its status updates across
#     different stages. This function sets up a test environment, monitors log outputs, and evaluates
#     expected results for various lifecycle stages of a cluster execution plan.
#
#     Parameters:
#         subtests (SubTests): A SubTests instance for managing multiple subtest contexts within
#                              a single test function.
#     """
#     logger("Setting up environment variables...")
#     for key, value in ENV_VARS.items():
#         os.environ[key] = value
#
#     stop_event = threading.Event()
#     observer = Observer()
#     event_handler = LogEventHandler(stop_event)
#     observer.schedule(event_handler, path=os.path.abspath("./"), recursive=False)
#
#     # Activate a policy, by renaming it
#     old_filename = f"policies/_policy-staticPlacement.py"
#     new_filename = f"policies/policy-staticPlacement.py"
#     rename_file(old_filename,new_filename)
#
#     # Runt agent
#     agent_process = run_agent()
#
#     try:
#         observer.start()
#         logger(f"Watching marker in {AGENT_LOG_PATH}: {EXPECTED_LOG_MARKER}")
#         if not stop_event.wait(timeout=30):
#             logger("Timeout: Marker not found in logs.")
#         else:
#             logger(f"Marker found: {EXPECTED_LOG_MARKER}")
#         agent_process.terminate()
#
#     finally:
#         observer.stop()
#         observer.join()
#         if agent_process.poll() is None:
#             agent_process.terminate()
#
#
#
#     # Restore and deactivate a policy, by renaming it
#     old_filename = f"policies/policy-staticPlacement.py"
#     new_filename = f"policies/_policy-staticPlacement.py"
#     rename_file(old_filename,new_filename)
#
#     # Step 1: Parse logs
#     parsed_logs = parse_test_logs()
#
#
#     # Step 2: Define the expected structure with updated stage names
#     expected_logs = {
#         "tasks_analyze.py": {
#             2: {"status": "True"}
#         },
#         "tasks_plan.py": {
#             1: {"policy": "staticPlacement"}
#         },
#         "mlsysops_scheduler.py": {
#             1: {"status": "Scheduled"}
#         },
#         "mechanisms_fluidity.py": {
#             1: {"status": "True"},
#             2: {"status": "MLSClusterAgent"},
#             3: {"status": "Success"}
#         },
#         "tasks_execute.py": {
#             1: {"status": "Pending"}
#         },
#         "fluidity_controller.py": {
#             1: {"status": "True"},
#             2: {"status": "Completed"}
#         },
#         "cluster_MLSClusterAgent.py": {
#             1: {"status": "Completed"}
#         }
#     }
#
#     aseert_payloads(subtests, expected_logs=expected_logs,parsed_logs=parsed_logs)

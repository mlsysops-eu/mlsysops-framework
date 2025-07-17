import socket
import os
import logging
from logging.handlers import RotatingFileHandler
import time
import signal
from threading import Thread
import mlstelemetry

mlsclient = mlstelemetry.MLSTelemetry("test", "client")

# Default client configurations
DEFAULT_IP = "localhost"
DEFAULT_PORT = 10000
LOG_FILE = "client.log"
LOG_FILE_MAX_SIZE = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 3  # Number of backup log files to keep

# Globals for statistics
running = True
success_count = 0
failed_connection_count = 0


def setup_logger():
    """Configure logger with RotatingFileHandler to handle log rotation."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # RotatingFileHandler for automatic log rotation
    rotating_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_FILE_MAX_SIZE, backupCount=LOG_BACKUP_COUNT
    )
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    rotating_handler.setFormatter(formatter)
    logger.addHandler(rotating_handler)

    # Console handler for printing logs to the console (optional)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    #logger.addHandler(mlsclient.getHandler())


def signal_handler(signum, frame):
    """Handle termination signals and stop the client."""
    global running
    logging.info(f"Received signal {signum}. Stopping client...")
    running = False


def statistics_monitor():
    """Logs statistics every 30 seconds."""
    global success_count, failed_connection_count
    while running:
        time.sleep(30)  # Wait for 30 seconds
        logging.info(
            f"Stats (last 30s): Successful sends: {success_count}, "
            f"Failed connections: {failed_connection_count}"
        )
        # Reset counters for the next interval
        success_count = 0
        failed_connection_count = 0


def start_client():
    """Start the TCP client."""
    global running, success_count, failed_connection_count

    # Get IP and port from environment variables
    ip = os.getenv("TCP_SERVER_IP", DEFAULT_IP)
    port = int(os.getenv("TCP_SERVER_PORT", DEFAULT_PORT))

    Thread(target=statistics_monitor, daemon=True).start()  # Start monitoring statistics
    total_count = 0
    while running:
        try:
            logging.info(f"Connecting to TCP server at {ip}:{port}...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5)  # Set timeout for connection

            try:
                # Attempt to connect to the server
                client_socket.connect((ip, port))
                logging.info("Connection established with the server.")

                while running:
                    # Send a message to the server (simulated payload)
                    payload = f"Hello from client at {time.time()}"
                    try:
                        client_socket.send(payload.encode("utf-8"))
                        total_count += 1
                        success_count += 1  # Increment successful send counter
                        mlsclient.pushMetric("test_sent_counter", "async_counter", total_count)
                        mlsclient.pushMetric("test_sent_success_counter", "async_counter", success_count)
                        logging.info(f"Sent message: {payload}")
                    except Exception as e:
                        logging.error(f"Error while sending data: {e}")
                        break

                    time.sleep(2)  # Simulate some delay between messages

            except socket.timeout:
                logging.warning("Connection attempt timed out.")
                failed_connection_count += 1  # Increment failed connection counter
            except Exception as e:
                logging.error(f"An error occurred: {e}")
                failed_connection_count += 1
            finally:
                client_socket.close()
                logging.info("Connection closed with the server.")
                time.sleep(5)  # Delay before attempting to reconnect

        except Exception as e:
            logging.error(f"Failed to connect to the server: {e}")
            failed_connection_count += 1  # Increment failed connection counter
            time.sleep(5)  # Delay before retrying

    logging.info("Client has stopped.")


if __name__ == "__main__":
    # Set up logging
    setup_logger()

    # Register signal handlers for graceful termination
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    start_client()
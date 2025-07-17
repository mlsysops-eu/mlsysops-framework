import socket
import os
import logging
from logging.handlers import RotatingFileHandler
import signal
import time
from threading import Thread
import mlstelemetry

mlsclient = mlstelemetry.MLSTelemetry("test", "server")

# Default server configurations
DEFAULT_IP = "localhost"
DEFAULT_PORT = 10000
LOG_FILE = "server.log"
LOG_FILE_MAX_SIZE = 50 * 1024 * 1024  # 50MB
LOG_BACKUP_COUNT = 1  # Number of backup log files to keep

# Globals for statistics
running = True
success_count = 0
disconnection_count = 0
disconnection_start_time = None
total_disconnection_time = 0
SOCKET_TIMEOUT = 1  # Timeout for the server socket in seconds (to allow SIGINT check)


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

    # logger.addHandler(mlsclient.getHandler())


def signal_handler(signum, frame):
    """Handle termination signals and stop the server."""
    global running
    logging.info(f"Received signal {signum}. Stopping server...")
    running = False


def statistics_monitor():
    """Logs statistics every 30 seconds."""
    global success_count, disconnection_count, total_disconnection_time
    while running:
        time.sleep(30)  # Wait for 30 seconds
        logging.info(
            f"Stats (last 30s): Received messages: {success_count}, "
            f"Disconnections: {disconnection_count}, "
            f"Total Disconnection Time (s): {total_disconnection_time:.2f}"
        )
        # Reset counters for the next interval
        success_count = 0
        disconnection_count = 0
        total_disconnection_time = 0


def start_server():
    global running, success_count, disconnection_count, disconnection_start_time, total_disconnection_time

    # Get IP and port from environment variables
    ip = os.getenv("TCP_SERVER_IP", DEFAULT_IP)
    port = int(os.getenv("TCP_SERVER_PORT", DEFAULT_PORT))

    Thread(target=statistics_monitor, daemon=True).start()  # Start monitoring statistics

    while running:
        try:
            logging.info(f"Starting TCP server on {ip}:{port}")
            
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((ip, port))
            server_socket.listen(1)  # Allow only one connection
            server_socket.settimeout(SOCKET_TIMEOUT)  # Set a timeout to allow graceful shutdown checks
            
            logging.info("Server is listening for connections...")
            disconnection_start_time = time.time()  # Track disconnected time
            total_count = 0
            while running:
                try:
                    # Wait for client connection within the timeout period
                    client_socket, client_address = server_socket.accept()
                    disconnection_end_time = time.time()

                    # Update disconnection time when a connection is established
                    if disconnection_start_time:
                        total_disconnection_time += disconnection_end_time - disconnection_start_time
                        disconnection_start_time = None

                    logging.info(f"Connection established with {client_address}")

                    try:
                        while running:
                            # Receive data from the client
                            data = client_socket.recv(1024)
                            if not data:
                                logging.info("Client disconnected.")
                                disconnection_start_time = time.time()
                                disconnection_count += 1
                                mlsclient.pushMetric("test_disconnection_counter", "async_counter", disconnection_count)

                                break

                            success_count += 1
                            total_count += 1
                            mlsclient.pushMetric("test_received_counter", "async_counter", total_count)
                            mlsclient.pushMetric("test_received_success_counter", "async_counter", success_count)
                            message = data.decode("utf-8")
                            logging.info(f"Received payload: {message}")

                    except Exception as e:
                        logging.error(f"Error while receiving data: {e}")

                    finally:
                        client_socket.close()
                        logging.info(f"Connection with {client_address} closed")
                
                except socket.timeout:
                    # Socket timed out; check `running` flag
                    if not running:
                        logging.info("Timeout occurred, shutting down gracefully after SIGINT.")
                        break

        except Exception as e:
            logging.error(f"Server encountered an error: {e}")
            logging.info("Retrying in 1 second...")
            time.sleep(1)  # Add delay to avoid rapid retries

        finally:
            try:
                server_socket.close()
            except Exception:
                pass

    logging.info("Server has stopped.")


if __name__ == "__main__":
    # Set up logging
    setup_logger()

    # Register signal handlers for graceful termination
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    start_server()
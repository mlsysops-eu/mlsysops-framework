import subprocess
import os
from dotenv import load_dotenv

def load_ip_from_env(env_file_path):
    # Load the environment variables from the .env file
    load_dotenv(env_file_path)
    host_ip = os.getenv("IP_SEL")  # Retrieve the IP_SEL variable from .env
    if host_ip is None:
        print("IP_SEL not found in the .env file.")
        return None
    return host_ip

def execute_docker_command(container_name, user, password, ip_address):
    """Runs a shell command using subprocess to register a user"""
    try:
        command = f"docker exec {container_name} ejabberdctl register {user} {ip_address} {password}"
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(result.stdout.decode("utf-8"))
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while registering {user}: {e.stderr.decode('utf-8')}")
        return False
    return True

def create_users(container_name, users_file_path, ip_address):
    # Read the users.txt file
    try:
        with open(users_file_path, "r") as file:
            for line in file:
                user_data = line.strip().split(",")  # Split each line into username and password
                if len(user_data) == 2:
                    user, password = user_data
                    print(f"Registering user: {user} with password: {password}")
                    execute_docker_command(container_name, user, password, ip_address)
                else:
                    print(f"Invalid format in users.txt: {line}")
    except FileNotFoundError:
        print(f"Error: {users_file_path} not found.")
    except Exception as e:
        print(f"Error reading the users file: {str(e)}")

def main():
    # Load IP address from the .env file
    env_file_path = ".env"  # Path to your .env file
    ip_address = load_ip_from_env(env_file_path)

    if ip_address is None:
        print("IP address could not be loaded from the .env file. Exiting.")
        return

    container_name = "ejabberd"  # Replace with your actual container name if different
    users_file_path = "users.txt"  # Path to the users.txt file

    # Create users from the users.txt file
    create_users(container_name, users_file_path, ip_address)

if __name__ == "__main__":
    main()

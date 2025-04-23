import os
from dotenv import load_dotenv
from ruamel.yaml import YAML

# Load the .env file and retrieve the HOST_IP
def load_ip_from_env(env_file_path):
    load_dotenv(env_file_path)  # Load the environment variables from the .env file
    host_ip = os.getenv("IP_SEL")  # Retrieve the HOST_IP variable
    if host_ip is None:
        print("IP_SEL not found in the .env file.")
        return None
    return host_ip

# Function to update the ejabberd.yml file
def update_ejabberd_config(yml_file_path, env_file_path):
    # Load the IP address from the .env file
    new_ip = load_ip_from_env(env_file_path)

    if new_ip is None:
        print("Could not determine the IP address.")
        return

    # Initialize ruamel.yaml to preserve formatting and comments
    yaml = YAML()
    yaml.preserve_quotes = True  # Optional: preserve quotes if necessary

    # Read the existing YAML file while preserving formatting
    with open(yml_file_path, 'r') as file:
        config = yaml.load(file)

    # Update the 'hosts' section with the IP address from the .env file
    if 'hosts' in config:
        config['hosts'] = [new_ip]

    # Update the 'acl -> admin -> user' section with the IP address from the .env file
    if 'acl' in config and 'admin' in config['acl'] and 'user' in config['acl']['admin']:
        config['acl']['admin']['user'] = [f'admin@{new_ip}', 'admin@localhost']

    # Write the updated configuration back to the file, preserving the formatting
    with open(yml_file_path, 'w') as file:
        yaml.dump(config, file)

    print(f"Updated ejabberd.yml with IP from .env: {new_ip}")

# Example usage:
yml_file_path = './ejabberd.yml'  # Update with the correct path to your ejabberd.yml file
env_file_path = './.env'  # Update with the correct path to your .env file

update_ejabberd_config(yml_file_path, env_file_path)

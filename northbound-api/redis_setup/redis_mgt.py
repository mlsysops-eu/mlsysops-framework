import redis
from redis_setup import redis_config as rc
import json
import time


class RedisManager:
    def __init__(self):
        """
        Initializes the connection to Redis.
        """
        self.host = rc.redis_host
        self.port = rc.redis_port
        self.db = rc.redis_db_number
        self.redis_conn = None
        self.redis_password = rc.redis_password
        self.q_name = rc.redis_queue_name
        self.ml_q = rc.redis_ml_queue
        self.channel_name = rc.redis_channel_name  # Channel name for Pub/Sub
        self.dict_name = rc.redis_dict_name  # Dictionary name (Redis hash map)

    def connect(self):
        """
        Establishes the connection to Redis.
        """
        try:
            self.redis_conn = redis.Redis(host=self.host, port=self.port, db=self.db, password=self.redis_password)
            # Verify connection
            if self.redis_conn.ping():
                print(f"Successfully connected to Redis at {self.host}.")
            else:
                raise Exception("Could not connect to Redis.")
        except redis.ConnectionError as e:
            print(f"Connection error: {e}")
            self.redis_conn = None

    # Queue methods
    def push(self, q_name, value: str):
        """
        Adds a value to the queue (push).
        """
        if self.redis_conn:
            self.redis_conn.rpush(q_name, value)
            print(f"'{value}' added to the queue '{q_name}'.")
        else:
            print("Redis connection not established. Use the 'connect' method first.")

    def pop(self, q_name):
        """
        Removes and returns the first element of the queue (pop).
        """
        if self.redis_conn:
            value = self.redis_conn.lpop(q_name)
            if value:
                print(f"'{value.decode()}' removed from the queue '{q_name}'.")
                return value.decode()
            else:
                print(f"The queue '{q_name}' is empty.")
                return None
        else:
            print("Redis connection not established. Use the 'connect' method first.")

    def is_empty(self, q_name):
        """
        Checks if the queue is empty.
        """
        if self.redis_conn:
            length = self.redis_conn.llen(q_name)
            return length == 0
        else:
            print("Redis connection not established. Use the 'connect' method first.")
            return True

    def empty_queue(self, q_name):
        """
        Empties the queue by removing all elements.
        """
        while not self.is_empty(q_name):
            self.pop(q_name)

    # Publish/Subscribe methods
    def pub_ping(self, message):
        """
        Publishes a message to a channel.
        :param message: Message to publish.
        """
        if self.redis_conn:
            self.redis_conn.publish(self.channel_name, message)
            print(f"'{message}' published to the channel '{self.channel_name}'.")
        else:
            print("Redis connection not established. Use the 'connect' method first.")

    def subs_ping(self):
        """
        Subscribes to a channel and listens for messages.
        """
        if self.redis_conn:
            pubsub = self.redis_conn.pubsub()
            pubsub.subscribe(self.channel_name)
            print(f"Subscribed to the channel '{self.channel_name}'.")

            # Listen for messages
            for message in pubsub.listen():
                if message and message['type'] == 'message':
                    print(f"Message received on channel '{self.channel_name}': {message['data'].decode()}")
        else:
            print("Redis connection not established. Use the 'connect' method first.")

    # Dictionary (Hash map) methods
    def update_dict_value(self, dict_name, key, value: str):
        """
        Updates the value of a key in a Redis dictionary (hash).
        :param dict_name:
        :param key: Key to update.
        :param value: New value to set.
        """

        if self.redis_conn:
            self.redis_conn.hset(dict_name, key, value)
            print(f"Value for key '{key}' updated to '{value}' in dictionary '{dict_name}'.")
        else:
            print("Redis connection not established. Use the 'connect' method first.")

    def get_dict_value(self, dict_name, key):
        """
        Gets the value associated with a key in a Redis dictionary (hash).
        :param key: Key whose value is to be retrieved.
        :return: The value of the key, or None if it does not exist.
        """
        if self.redis_conn:
            value = self.redis_conn.hget(dict_name, key)
            if value:
                print(f"Value for key '{key}' in dictionary '{dict_name}': {value.decode()}")
                return value.decode()
            else:
                print(f"Key '{key}' does not exist in dictionary '{dict_name}'.")
                return None
        else:
            print("Redis connection not established. Use the 'connect' method first.")

    def get_dict(self, dict_name):
        """
        Retrieves all key-value pairs from the Redis hash.
        """
        try:
            redis_dict = self.redis_conn.hgetall(dict_name)
            # Convert byte keys and values to strings (since Redis returns bytes)
            return {key.decode('utf-8'): value.decode('utf-8') for key, value in redis_dict.items()}
        except Exception as e:
            print(f"Error retrieving Redis dictionary: {e}")
            return None

    def remove_key(self, dict_name, key):
        """
        Deletes a key-value pair from the Redis hash.

        Parameters:
        - dict_name (str): The name of the hash.
        - key (str): The key to delete from the hash.

        Returns:
        - bool: True if the key was deleted, False if the key does not exist or an error occurred.
        """
        try:
            # Attempt to delete the key from the hash
            result = self.redis_conn.hdel(dict_name, key)

            # Return True if a key was deleted (hdel returns the number of keys deleted)
            return bool(result)
        except Exception as e:
            print(f"Error deleting key from Redis hash: {e}")
            return False

    def value_in_hash(self, dict_name, app_id):
        """
        Checks if a given app_id exists as a key in the specified Redis hash.

        :param dict_name: The name of the Redis hash.
        :param app_id: The key to check in the hash.
        :return: True if the app_id exists, False otherwise.
        """
        if self.redis_conn:
            exists = self.redis_conn.hexists(dict_name, app_id)
            if exists:
                print(f"The key '{app_id}' exists in the dictionary '{dict_name}'.")
            else:
                print(f"The key '{app_id}' does not exist in the dictionary '{dict_name}'.")
            return exists
        else:
            print("Redis connection not established. Use the 'connect' method first.")
            return False

    def json_update(self, key, path, json_data):
        """
        Updates an existing JSON object at the specified key and path.
        """
        try:
            # Retrieve the existing JSON data
            existing_data = self.redis_conn.execute_command("JSON.GET", key, "$")
            if not existing_data:
                return f"No existing data found for key: {key}. Cannot update."

            # Decode and clean the JSON string
            existing_data = existing_data.decode('utf-8') if isinstance(existing_data, bytes) else existing_data
            if existing_data.startswith("[") and existing_data.endswith("]"):
                existing_data = existing_data[1:-1]

            # Convert the existing JSON to a dictionary
            existing_dict = json.loads(existing_data)

            # Ensure json_data is a dictionary
            if isinstance(json_data, str):
                json_data = json.loads(json_data)

            # Merge the dictionaries
            continuum_id = json_data.get("MLSysOpsContinuum", {}).get("continuumID")
            if continuum_id:
                for cluster in json_data["MLSysOpsContinuum"].get("clusters", []):
                    if cluster in existing_dict.get("MLSysOpsContinuum", {}).get("clusters", []):
                        # Perform cluster-specific updates here
                        pass
                    else:
                        existing_dict["MLSysOpsContinuum"].setdefault("clusters", []).append(cluster)
            else:
                existing_dict.update(json_data)

            # Update the JSON data in Redis
            self.redis_conn.execute_command("JSON.SET", key, path, json.dumps(existing_dict))
            return f"JSON data updated successfully at key: {key}, path: {path}"
        except redis.RedisError as e:
            return f"Error updating JSON data: {e}"
        except json.JSONDecodeError as e:
            return f"Error decoding JSON data: {e}"

    def json_set(self, key, path, json_data):
        """
        Sets or updates a JSON object at the specified key and path.
        """
        try:
            # Check if the JSON key already exists
            existing_data = self.redis_conn.execute_command("JSON.GET", key, "$")

            if not existing_data:
                # If no existing data, create the new JSON structure
                self.redis_conn.execute_command("JSON.SET", key, path, json_data)
                return f"JSON data created successfully at key: {key}, path: {path}"
            else:
                self.json_update(key, path, json_data)
        except redis.RedisError as e:
            return f"Error setting JSON data: {e}"

    def json_get(self, key, path="$"):
        """
        Retrieves JSON data from the specified key and path.
        """
        try:
            result = self.redis_conn.execute_command("JSON.GET", key, path)
            return result if result else f"No data found at key: {key}, path: {path}"
        except redis.RedisError as e:
            return f"Error retrieving JSON data: {e}"

    def json_delete(self, key, path="$"):
        """
        Deletes JSON data at the specified key and path.
        """
        try:
            result = self.redis_conn.execute_command("JSON.DEL", key, path)
            return f"Deleted JSON at key: {key}, path: {path}" if result else f"No JSON data found to delete at key: {key}, path: {path}"
        except redis.RedisError as e:
            return f"Error deleting JSON data: {e}"

    def add_components(self, app_id, component_ids):
        """
        Adds a list of components to the component list of an application in Redis.

        Parameters:
            app_id (str): The ID of the application.
            component_ids (list): A list of component IDs to be added.
        """
        if self.redis_conn:
            if isinstance(component_ids, list):
                for component_id in component_ids:
                    self.redis_conn.rpush(f"app_components_list:{app_id}", component_id)
                print(f"Components {component_ids} added to application '{app_id}'.")
            else:
                print("Error: component_ids should be a list.")
        else:
            print("Redis connection not established.")

    def get_components(self, app_id):
        """
        Retrieves all components associated with an application.
        """
        if self.redis_conn:
            components = self.redis_conn.lrange(f"app_components_list:{app_id}", 0, -1)
            return [c.decode('utf-8') for c in components]
        else:
            print("Redis connection not established.")
            return []

    def update_component(self, component_id, details):
        """
        Updates the details of a component in a hash.
        """
        if self.redis_conn:
            self.redis_conn.hset(f"component_hash:{component_id}", mapping=details)
            print(f"Component '{component_id}' updated with details: {details}")
        else:
            print("Redis connection not established.")

    def get_component_details(self, component_id):
        """
        Retrieves the details of a component.
        """
        if self.redis_conn:
            details = self.redis_conn.hgetall(f"component_hash:{component_id}")
            return {k.decode('utf-8'): v.decode('utf-8') for k, v in details.items()}
        else:
            print("Redis connection not established.")
            return {}

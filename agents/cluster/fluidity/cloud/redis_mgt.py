import redis
import redis_config as rc

class RedisManager:
    def __init__(self):
        """
        Initializes the connection to Redis.
        """
        self.host = rc.redis_host
        self.port = rc.redis_port
        self.db = rc.redis_db_number
        self.password = rc.redis_password
        self.redis_conn = None
        self.channel_name = rc.redis_channel_name  # Channel name for Pub/Sub
        #self.dict_name = rc.redis_dict_name  # Dictionary name (Redis hash map)

    def connect(self):
        """
        Establishes the connection to Redis.
        """
        try:
            self.redis_conn = redis.Redis(host=self.host, port=self.port, db=self.db,password=self.password)
            # Verify connection
            if self.redis_conn.ping():
                print(f"Successfully connected to Redis at {self.host}.")
            else:
                raise Exception("Could not connect to Redis.")
        except redis.ConnectionError as e:
            print(f"Connection error: {e}")
            self.redis_conn = None

    # Queue methods
    def push(self, q_name, value):
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

    def empty_queue(self):
        """
        Empties the queue by removing all elements.
        """
        while not self.is_empty():
            self.pop()

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
    def update_dict_value(self, dict_name, key, value):
        """
        Updates the value of a key in a Redis dictionary (hash).
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
        Retrieves all key-value pairs from the Redis hash named 'app_dict'.
        """
        try:
            redis_dict = self.redis_conn.hgetall(dict_name)
            # Convert byte keys and values to strings (since Redis returns bytes)
            return {key.decode('utf-8'): value.decode('utf-8') for key, value in redis_dict.items()}
        except Exception as e:
            print(f"Error retrieving Redis dictionary: {e}")
            return None
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

import json
import os
import redis
from ..logger_util import logger

# Fetching environment variables with default values if not set
redis_host = os.getenv('REDIS_HOST', '172.25.27.72')  # Default to '10.96.12.155'
redis_port = int(os.getenv('REDIS_PORT', 6379))  # Default to 6379
redis_db_number = int(os.getenv('REDIS_DB_NUMBER', 0))  # Default to 0
redis_password = os.getenv('REDIS_PASSWORD', 'secret')  # Uncomment if password is needed
redis_queue_name = os.getenv('REDIS_QUEUE_NAME', 'valid_descriptions_queue')  # Default queue name
redis_channel_name = os.getenv('REDIS_CHANNEL_NAME', 'my_channel')  # Default channel name
redis_dict_name = os.getenv('REDIS_DICT_NAME', 'system_app_hash')  # Default dictionary name
redis_dict2_name = os.getenv('REDIS_DICT2_NAME', 'component_metrics')  # Components hash
redis_ml_queue = os.getenv('REDIS_ML_QUEUE_NAME', 'ml_deployment_queue')  # Default channel name ""


class RedisManager:
    def __init__(self):
        """
        Initializes the connection to Redis.
        """
        self.host = redis_host
        self.port = redis_port
        self.db = redis_db_number
        self.redis_conn = None
        self.redis_password = redis_password
        self.q_name = redis_queue_name
        self.ml_q = redis_ml_queue
        self.channel_name = redis_channel_name  # Channel name for Pub/Sub
        self.dict_name = redis_dict_name  # Dictionary name (Redis hash map)
        self.redis_dict = "cluster_agents"
        self.redis_agents = "system_agents"

    def connect(self):
        """
        Establishes the connection to Redis.
        """
        try:
            self.redis_conn = redis.Redis(host=self.host, port=self.port, db=self.db, password=self.redis_password)
            if self.redis_conn.ping():
                logger.info(f"Successfully connected to Redis at {self.host}.")
            else:
                raise Exception("Could not connect to Redis.")
        except redis.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            self.redis_conn = None

    # --- Queue Methods ---
    def push(self, q_name, value):
        if self.redis_conn:
            self.redis_conn.rpush(q_name, value)
            print(f"'{value}' added to the queue '{q_name}'.")
        else:
            print("Redis connection not established.")

    def pop(self, q_name):
        if self.redis_conn:
            value = self.redis_conn.lpop(q_name)
            if value:
                #print(f"'{value.decode()}' removed from the queue '{q_name}'.")
                logger.debug(f" Info removed from '{q_name}'.")
                return value.decode()
            print(f"The queue '{q_name}' is empty.")
        else:
            print("Redis connection not established.")

    def is_empty(self, q_name):
        return self.redis_conn.llen(q_name) == 0 if self.redis_conn else True

    def empty_queue(self, q_name):
        while not self.is_empty(q_name):
            self.pop(q_name)

    # --- Pub/Sub Methods ---
    def pub_ping(self, message):
        if self.redis_conn:
            self.redis_conn.publish(self.channel_name, message)
            print(f"'{message}' published to the channel '{self.channel_name}'.")
        else:
            print("Redis connection not established.")

    def subs_ping(self):
        if self.redis_conn:
            pubsub = self.redis_conn.pubsub()
            pubsub.subscribe(self.channel_name)
            print(f"Subscribed to the channel '{self.channel_name}'.")
            for message in pubsub.listen():
                if message and message['type'] == 'message':
                    print(f"Message received: {message['data'].decode()}")
        else:
            print("Redis connection not established.")

    # --- Dictionary (Hash Map) Methods ---
    def update_dict_value(self, dict_name, key, value):
        if self.redis_conn:
            self.redis_conn.hset(dict_name, key, value)
            print(f"Value for key '{key}' updated to '{value}' in dictionary '{dict_name}'.")
        else:
            print("Redis connection not established.")

    def get_dict_value(self, dict_name, key):
        if self.redis_conn:
            value = self.redis_conn.hget(dict_name, key)
            return value.decode() if value else None
        print("Redis connection not established.")

    def get_dict(self, dict_name):
        if self.redis_conn:
            return {k.decode(): v.decode() for k, v in self.redis_conn.hgetall(dict_name).items()}
        print("Redis connection not established.")

    def remove_key(self, dict_name, key):
        return bool(self.redis_conn.hdel(dict_name, key)) if self.redis_conn else False

    def value_in_hash(self, dict_name, key):
        return self.redis_conn.hexists(dict_name, key) if self.redis_conn else False

    # --- JSON Operations ---
    def json_set(self, key, path, json_data):
        try:
            if not self.redis_conn.execute_command("JSON.GET", key, "$"):
                self.redis_conn.execute_command("JSON.SET", key, path, json_data)
                return f"JSON data created at key: {key}, path: {path}"
            return self.json_update(key, path, json_data)
        except redis.RedisError as e:
            return f"Error setting JSON data: {e}"

    def json_get(self, key, path="$"):
        return self.redis_conn.execute_command("JSON.GET", key, path) if self.redis_conn else None

    def json_update(self, key, path, json_data):
        try:
            existing_data = self.json_get(key)
            if not existing_data:
                return f"No existing data for key: {key}."

            existing_dict = json.loads(existing_data)
            if isinstance(json_data, str):
                json_data = json.loads(json_data)

            existing_dict.update(json_data)
            self.redis_conn.execute_command("JSON.SET", key, path, json.dumps(existing_dict))
            return f"JSON updated at key: {key}, path: {path}"
        except Exception as e:
            return f"Error updating JSON: {e}"

    def json_delete(self, key, path="$"):
        return self.redis_conn.execute_command("JSON.DEL", key, path) if self.redis_conn else None

    # --- Component Management ---
    def add_components(self, app_id, component_ids):
        if self.redis_conn and isinstance(component_ids, list):
            for component_id in component_ids:
                self.redis_conn.rpush(f"app_components_list:{app_id}", component_id)

    def get_components(self, app_id):
        return [c.decode() for c in
                self.redis_conn.lrange(f"app_components_list:{app_id}", 0, -1)] if self.redis_conn else []

    def update_component(self, component_id, details):
        self.redis_conn.hset(f"component_hash:{component_id}", mapping=details) if self.redis_conn else None

    def get_component_details(self, component_id):
        return {k.decode(): v.decode() for k, v in
                self.redis_conn.hgetall(f"component_hash:{component_id}").items()} if self.redis_conn else {}

    def delete_component(self, app_id):
        self.redis_conn.delete(f"app_components_list:{app_id}") if self.redis_conn else None

    def json_app_hash(self, app_id, app_data):
        if self.redis_conn:
            self.redis_conn.hset("app_hash", app_id, json.dumps(app_data))

    def delete_app_components_from_hash(self, hash_name, app_id):
        if self.redis_conn:
            keys_to_delete = [key.decode() for key in self.redis_conn.hkeys(hash_name) if app_id in key.decode()]
            if keys_to_delete:
                self.redis_conn.hdel(hash_name, *keys_to_delete)

    # --- Infrastructure Management ---
    def add_cluster(self, cluster_id, nodes):
        for node in nodes:
            self.redis_conn.sadd(f"MLSysOpsCluster:{cluster_id}:Nodes", node)

    def list_clusters_in_continuum(self, continuum_id):
        return [c.decode() for c in self.redis_conn.smembers(f"MLSysOpsContinuum:{continuum_id}:Clusters")]

    def list_nodes_in_cluster(self, cluster_id):
        return [n.decode() for n in self.redis_conn.smembers(f"MLSysOpsCluster:{cluster_id}:Nodes")]

    def add_datacenter(self, datacenter_id, cluster_id, continuum, nodes):
        self.redis_conn.hset(f"MLSysOpsDatacenter:{datacenter_id}",
                             mapping={"clusterID": cluster_id, "continuum": continuum})
        for node in nodes:
            self.redis_conn.sadd(f"MLSysOpsDatacenter:{datacenter_id}:Nodes", node)

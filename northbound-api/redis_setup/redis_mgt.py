import json

import redis
from redis_setup import redis_config as rc


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
    def push(self, q_name, value):
        """
        Adds a value to the queue (push).
        """
        if self.redis_conn:
            self.redis_conn.rpush(q_name, value)
            print(f"File successfully  added to the queue '{q_name}'.")
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

    def value_in_hash(self, hash_name, key):
        """
        Checks if a specific key exists in a Redis hash.

        Parameters:
        - hash_name (str): The name of the hash.
        - key (str): The key to check for existence in the hash.

        Returns:
        - bool: True if the key exists in the hash, False otherwise.
        """
        try:
            # Check if the key exists in the specified hash
            return self.redis_conn.hexists(hash_name, key)
        except Exception as e:
            print(f"Error checking key existence in Redis hash: {e}")
            return False

    # --- Infrastructure Management Functions ---
    def add_continuum(self, continuum_id, clusters):
        """
        Adds a new continuum and associates it with a list of clusters.

        :param continuum_id: Unique identifier for the continuum.
        :param clusters: List of cluster IDs to associate with this continuum.
        :return: Confirmation message.
        """
        if not clusters or not isinstance(clusters, list):
            return {"error": "Clusters must be a non-empty list."}

        # Store the continuum in Redis
        self.redis_conn.sadd("MLSysOpsContinuum:ContinuumIDs", continuum_id)
        for cluster in clusters:
            self.redis_conn.sadd(f"MLSysOpsContinuum:{continuum_id}:Clusters", cluster)

        return {"message": f"Continuum {continuum_id} added with clusters: {clusters}"}

    def add_cluster_to_continuum(self, cluster_id):
        self.redis_conn.sadd("MLSysOpsContinuum:Continuum:Clusters", cluster_id)
        return {"message": f"Cluster {cluster_id} added to continuum."}

    def add_node_to_cluster(self, cluster_id, node_id, node_data):
        """
        Adds a node to a cluster and stores its configuration.

        :param cluster_id: The ID of the cluster.
        :param node_id: The ID of the node.
        :param node_data: Full node configuration.
        :return: Confirmation message.
        """
        # Store node configuration
        self.redis_conn.hset(f"MLSysOpsNode:{node_id}", mapping=node_data)

        # Add the node to the cluster's node set
        self.redis_conn.sadd(f"MLSysOpsCluster:{cluster_id}:Nodes", node_id)

        return {"message": f"Node {node_id} added to Cluster {cluster_id}."}

    def add_datacenter(self, datacenter_id, cluster_id, continuum, nodes):
        """
        Registers a datacenter within a cluster.

        :param datacenter_id: Unique identifier for the datacenter.
        :param cluster_id: Cluster to which the datacenter belongs.
        :param continuum: Continuum layer (Cloud, Edge, etc.).
        :param nodes: List of node IDs in the datacenter.
        :return: Confirmation message.
        """
        # Check if the cluster exists
        if not self.redis_conn.exists(f"MLSysOpsCluster:{cluster_id}"):
            return {"error": f"ErrorInvalidDatacenterID: Cluster {cluster_id} is not registered."}

        # Register datacenter
        self.redis_conn.hset(f"MLSysOpsDatacenter:{datacenter_id}", mapping={
            "datacenterID": datacenter_id,
            "clusterID": cluster_id,
            "continuum": continuum
        })

        # Add nodes to the datacenter
        for node in nodes:
            self.redis_conn.sadd(f"MLSysOpsDatacenter:{datacenter_id}:Nodes", node)

        return {"message": f"Datacenter {datacenter_id} registered in Cluster {cluster_id} with nodes: {nodes}"}

    def list_infrastructure(self, identifier):
        if identifier == "0":
            datacenters = self.redis_conn.keys("MLSysOpsDatacenter:*")
            datacenter_ids = [dc.split(":")[-1] for dc in datacenters]
            return datacenter_ids if datacenter_ids else "ErrorInvalidDatacenterID"
        elif self.redis_conn.exists(f"MLSysOpsDatacenter:{identifier}"):
            clusters = self.redis_conn.smembers(f"MLSysOpsCluster:{identifier}:Datacenters")
            return clusters if clusters else "ErrorInvalidDatacenterID"
        elif self.redis_conn.exists(f"MLSysOpsCluster:{identifier}"):
            nodes = self.redis_conn.smembers(f"MLSysOpsCluster:{identifier}:Nodes")
            return nodes if nodes else "ErrorInvalidClusterID"
        else:
            return "ErrorInvalidClusterID"

    def unregister_infrastructure(self, ids):
        for identifier in ids:
            if self.redis_conn.exists(f"MLSysOpsDatacenter:{identifier}"):
                self.redis_conn.delete(f"MLSysOpsDatacenter:{identifier}")
                return 0
            elif self.redis_conn.exists(f"MLSysOpsCluster:{identifier}"):
                self.redis_conn.delete(f"MLSysOpsCluster:{identifier}")
                return 0
            elif self.redis_conn.exists(f"MLSysOpsNode:{identifier}"):
                self.redis_conn.delete(f"MLSysOpsNode:{identifier}")
                return 0
            else:
                return "ErrorInvalidID"
        return 0

    def add_standalone_node(self, node_id, node_data):
        """
        Adds a standalone node (not associated with any cluster or datacenter).

        :param node_id: The ID of the standalone node.
        :param node_data: Full node configuration.
        :return: Confirmation message.
        """
        standalone_nodes_key = "MLSysOpsStandaloneNodes"

        # Store the standalone node's configuration
        self.redis_conn.hset(f"MLSysOpsNode:{node_id}", mapping=node_data)

        # Add the node to the standalone nodes set
        self.redis_conn.sadd(standalone_nodes_key, node_id)

        return {"message": f"Standalone node {node_id} registered successfully."}

    def add_node_to_datacenter(self, datacenter_id, node_id, node_data):
        """
        Adds a node to a datacenter and stores its configuration.

        :param datacenter_id: The ID of the datacenter.
        :param node_id: The ID of the node.
        :param node_data: Full node configuration.
        :return: Confirmation message.
        """
        # Store node configuration
        self.redis_conn.hset(f"MLSysOpsNode:{node_id}", mapping=node_data)

        # Add the node to the datacenter's node set
        self.redis_conn.sadd(f"MLSysOpsDatacenter:{datacenter_id}:Nodes", node_id)

        return {"message": f"Node {node_id} added to Datacenter {datacenter_id}."}

    def add_cluster(self, cluster_id, nodes):
        """
        Registers a cluster and associates nodes with it.

        :param cluster_id: The unique identifier for the cluster.
        :param nodes: List of node IDs to associate with this cluster.
        :return: Confirmation message.
        """
        # Check if cluster exists in a registered continuum
        continuum_keys = self.redis_conn.keys("MLSysOpsContinuum:*")
        found_continuum = None
        for continuum_key in continuum_keys:
            continuum_id = continuum_key.decode().split(":")[-1]
            clusters_in_continuum = {c.decode() for c in
                                     self.redis_conn.smembers(f"MLSysOpsContinuum:Continuum:Clusters")}
            if cluster_id in clusters_in_continuum:
                found_continuum = continuum_id
                break

        if not found_continuum:
            return {
                "error": f"ErrorInvalidClusterID: Cluster {cluster_id} is not associated with any registered continuum."}

        # Register cluster
        #self.redis_conn.sadd(f"MLSysOpsContinuum:{found_continuum}:Clusters", cluster_id)

        # Add nodes to the cluster
        for node in nodes:
            self.redis_conn.sadd(f"MLSysOpsCluster:{cluster_id}:Nodes", node)

        return {"message": f"Cluster {cluster_id} registered in Continuum {found_continuum} with nodes: {nodes}"}

    def list_datacenters(self):
        """
        Retrieves all datacenter IDs in the system.

        :return: List of datacenter IDs.
        """
        datacenter_keys = self.redis_conn.keys("MLSysOpsDatacenter:*")

        # Extract only valid Datacenter IDs (excluding node sets)
        datacenter_ids = [key.decode().split(":")[1] for key in datacenter_keys if b'Nodes' not in key]

        return {"Datacenters": datacenter_ids}

    def list_clusters_in_continuum(self, continuum_id):
        """
        Lists all clusters in a given continuum.

        :param continuum_id: The unique identifier for the continuum.
        :return: List of cluster IDs in the continuum or an error message.
        """
        continuum_clusters_key = f"MLSysOpsContinuum:{continuum_id}:Clusters"

        # Check if the continuum exists
        if not self.redis_conn.exists(continuum_clusters_key):
            return {"error": "ErrorInvalidContinuumID: Continuum does not exist."}

        # Retrieve clusters from the set
        clusters = {cluster.decode() for cluster in self.redis_conn.smembers(continuum_clusters_key)}
        return {"ContinuumID": continuum_id, "Clusters": list(clusters)}

    def list_nodes_in_cluster(self, cluster_id):
        """
        Lists all nodes in a given cluster.

        :param cluster_id: The unique identifier for the cluster.
        :return: List of node IDs in the cluster or an error message.
        """
        cluster_nodes_key = f"MLSysOpsCluster:{cluster_id}:Nodes"

        # Check if the cluster exists
        if not self.redis_conn.exists(cluster_nodes_key):
            return {"error": "ErrorInvalidClusterID: Cluster does not exist."}

        # Retrieve nodes from the set
        nodes = {node.decode() for node in self.redis_conn.smembers(cluster_nodes_key)}
        return {"ClusterID": cluster_id, "Nodes": list(nodes)}

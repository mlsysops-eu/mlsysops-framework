import subprocess
import json
import os

def get_karmada_pods(cluster_name):
    """
    Get the pods from a Karmada cluster using kubectl.

    :param cluster_name: The name of the Karmada cluster to query.
    :return: List of pods in the specified cluster or None if an error occurs.
    """
    try:
        # Prepare the environment variables (use the current environment)
        env_vars = os.environ.copy()

        # Run the kubectl command to get the pods in the cluster
        result = subprocess.run(
            ["kubectl", "get", "pods", "--context", cluster_name, "-o", "json"],
            check=True, text=True, capture_output=True, env=env_vars
        )

        # Parse the JSON output from the kubectl command
        pods = json.loads(result.stdout)

        # Return the parsed pod data
        return pods

    except subprocess.CalledProcessError as e:
        print(f"Error executing kubectl command: {e.stderr}")
        return None

if __name__ == "__main__":
    # Replace this with your actual cluster name
    cluster_name = "your-karmada-cluster-name"

    # Get pods from the cluster
    pods = get_karmada_pods(cluster_name)

    # Print the result
    if pods:
        print("Pods retrieved successfully:")
        for pod in pods.get("items", []):
            pod_name = pod["metadata"].get("name", "Unknown")
            pod_status = pod["status"].get("phase", "Unknown")
            print(f"Pod name: {pod_name}, Status: {pod_status}")
    else:
        print("Failed to retrieve pods. Make sure the cluster name is correct and kubectl is configured.")

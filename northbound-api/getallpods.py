import subprocess
from agents.mlsysops.logger_util import logger

# Define kubeconfig files
karmada_api_kubeconfig = "/home/runner/karmada_management/karmada-api.kubeconfig"
uth_dev_kubeconfig = "/home/runner/karmada_management/uth-dev.kubeconfig"
uth_prod_kubeconfig = "/home/runner/karmada_management/uth-prod.kubeconfig"

# List of kubeconfig files to check
kubeconfigs = [karmada_api_kubeconfig, uth_dev_kubeconfig, uth_prod_kubeconfig]

def get_pods_from_kubeconfigs():
    """
    Retrieve all pods from multiple clusters using specified kubeconfig files.

    Returns:
        list: A list of dictionaries containing pod details (name, status, node, cluster).
    """
    pod_details = []

    for kubeconfig in kubeconfigs:
        try:
            # Retrieve contexts for the given kubeconfig
            result = subprocess.run(
                ["kubectl", "config", "get-contexts", "-o", "name", "--kubeconfig", kubeconfig],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                pod_details.append({"error": f"Error fetching contexts from {kubeconfig}: {result.stderr.strip()}"})
                continue

            contexts = result.stdout.strip().split("\n")

            # Fetch pod information for each context
            for context_name in contexts:
                try:
                    pod_result = subprocess.run(
                        [
                            "kubectl",
                            "get",
                            "pods",
                            "--context",
                            context_name,
                            "--kubeconfig",
                            kubeconfig,
                            "-o",
                            "custom-columns=NAME:.metadata.name,STATUS:.status.phase,NODE:.spec.nodeName",
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )

                    if pod_result.returncode != 0:
                        pod_details.append({"error": f"Error fetching pods for context {context_name} ({kubeconfig}): {pod_result.stderr.strip()}"})
                        continue

                    # Parse the output and collect pod details
                    lines = pod_result.stdout.strip().split("\n")
                    if len(lines) > 1:  # Skip header row
                        for line in lines[1:]:
                            parts = line.split()
                            if len(parts) >= 3:  # Ensure there are enough columns
                                name, status, node = parts
                                pod_details.append({
                                    "pod_name": name,
                                    "pod_status": status,
                                    "node_name": node,
                                    "cluster_name": context_name,
                                    "kubeconfig": kubeconfig,
                                })

                except Exception as e:
                    pod_details.append({"error": f"Error while listing pods for context {context_name} ({kubeconfig}): {str(e)}"})

        except Exception as e:
            pod_details.append({"error": f"Error while retrieving contexts from {kubeconfig}: {str(e)}"})

    return pod_details

def main():
    """
    Main function to fetch and display pod details from multiple kubeconfig files.
    """
    pod_details = get_pods_from_kubeconfigs()

    if isinstance(pod_details, list):
        for pod in pod_details:
            if "error" in pod:
                logger.error(f"❌ {pod['error']}")
            else:
                logger.info(f"✅ Pod: {pod['pod_name']}, Status: {pod['pod_status']}, Node: {pod['node_name']}, "
                      f"Cluster: {pod['cluster_name']}, Kubeconfig: {pod['kubeconfig']}")
    else:
        logger.error("Unexpected error: pod_details is not a list")

if __name__ == "__main__":
    main()

import yaml
from fastapi import APIRouter, HTTPException, Request
import json
from redis_setup import redis_mgt as rm
from jsonschema import validate, ValidationError
import requests
from MLSysOps_Schemas.mlsysops_schemas import app_schema
import subprocess
from kubernetes import client, config

# JSON schema with enum validation for the city
# Update the required fields in the JSON schema
schema = app_schema



karmada_api_kubeconfig = "/home/runner/karmada_management/karmada-api.kubeconfig"
uth_dev_kubeconfig ="/home/runner/karmada_management/uth-dev.kubeconfig"
uth_prod_kubeconfig = "/home/runner/karmada_management/uth-prod.kubeconfig"

def get_contexts_and_pods():
    """
    Retrieve all available contexts and fetch pod information for each, including pod name, status, node, and cluster.

    Returns:
        list: A list of dictionaries containing pod details (name, status, node, cluster).
    """
    try:
        # Retrieve contexts using kubectl
        result = subprocess.run(
            ["kubectl", "config", "get-contexts", "-o", "name"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            return {"error": f"Error fetching contexts: {result.stderr.strip()}"}

        contexts = result.stdout.strip().split("\n")
        pod_details = []

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
                        "-o",
                        "custom-columns=NAME:.metadata.name,STATUS:.status.phase,NODE:.spec.nodeName",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                if pod_result.returncode != 0:
                    pod_details.append({"error": f"Error fetching pods for context {context_name}: {pod_result.stderr.strip()}"})
                    continue

                # Parse the output and collect pod details
                lines = pod_result.stdout.strip().split("\n")
                if len(lines) > 1:  # Skip header row
                    for line in lines[1:]:
                        name, status, node = line.split()
                        pod_details.append({
                            "pod_name": name,
                            "pod_status": status,
                            "node_name": node,
                            "cluster_name": context_name,
                        })

            except Exception as e:
                pod_details.append({"error": f"Error while listing pods for context {context_name}: {str(e)}"})

        return pod_details

    except Exception as e:
        return {"error": f"Error while retrieving contexts: {str(e)}"}
def list_clusters_and_pods_from_karmada():
    """
    Retrieve the list of clusters and their pods from Karmada.

    :return: Dictionary with cluster names as keys and pod details as values.
    """
    try:
        # Load Karmada control plane kubeconfig
        config.load_kube_config(config_file=karmada_api_kubeconfig)

        # Karmada clusters API endpoint
        group = "cluster.karmada.io"
        version = "v1alpha1"
        plural = "clusters"

        # Create Karmada Custom Objects API client
        custom_object_api = client.CustomObjectsApi()

        # Retrieve the list of clusters registered to Karmada
        clusters = custom_object_api.list_cluster_custom_object(group, version, plural)

        clusters_and_pods = {}

        for cluster in clusters.get("items", []):
            cluster_name = cluster.get("metadata", {}).get("name", "Unknown")

            if cluster_name == 'uth-dev-cluster':
                config.load_kube_config(config_file=uth_dev_kubeconfig)
            elif cluster_name == 'uth-prod-cluster':
                config.load_kube_config(config_file=uth_prod_kubeconfig)
            else:
                print(f"Cluster {cluster_name} does not have kubeconfig information.")
                continue

            # Create a CoreV1Api client to access the cluster
            core_v1_api = client.CoreV1Api()

            pods_in_cluster = []

            try:
                # List pods for the default namespace
                pods = core_v1_api.list_namespaced_pod(namespace='default')
                for pod in pods.items:
                    pod_details = {
                        "namespace": pod.metadata.namespace,
                        "name": pod.metadata.name,
                        "status": pod.status.phase
                    }
                    pods_in_cluster.append(pod_details)
            except client.ApiException as e:
                print(f"  Error retrieving pods for cluster {cluster_name}: {e}")

            clusters_and_pods[cluster_name] = pods_in_cluster

        return clusters_and_pods

    except Exception as e:
        print(f"Error: {e}")
        return {}  # Return an empty dictionary in case of errors
def get_yaml_info(data):
    """
    Extracts the application name and components from a dictionary.

    Parameters:
        data (dict): Dictionary containing the application data.

    Returns:
        tuple: A tuple with the application name and a list of component names.
    """
    try:
        # Extract the application name
        app_name = data.get("MLSysOpsApplication", {}).get("name", None)

        # Extract the component names
        components = [
            component.get("Component", {}).get("name", None)
            for component in data.get("MLSysOpsApplication", {}).get("components", [])
            if component.get("Component", {}).get("name", None)
        ]

        return app_name, components
    except Exception as e:
        print(f"Error processing the data: {e}")
        return None, []


def get_karmada_pods(cluster_name):
    """
    Retrieves the pods in a specific cluster using kubectl and the Karmada context.
    """
    try:
        # Execute the `kubectl get pods` command
        result = subprocess.run(
            ["kubectl", "get", "pods", "--context", cluster_name, "-o", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        # Parse the JSON output
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error fetching pods from cluster '{cluster_name}': {e}")


def mock_karmada_pods():
    return [
        {
            "metadata": {"name": "tractor-app-pod", "labels": {"app": "tractor-app"}},
            "status": {"phase": "Running"}
        },
        {
            "metadata": {"name": "drone-app-pod", "labels": {"app": "drone-app"}},
            "status": {"phase": "Pending"}
        }
    ]


def validate_yaml(json_data):
    try:
        validate(instance=json_data, schema=schema)
        return None
    except ValidationError as e:
        return e.message
    except Exception as e:
        return str(e)


router = APIRouter()

# Connect to Redis using RedisManager
r = rm.RedisManager()
r.connect()

# Global variable to store the last connection time
last_connection_time = None

"----------------------------------------------------------------------------------------"
"            DEPLOY APP                                                                  "
"----------------------------------------------------------------------------------------"


@router.post("/deploy", tags=["Apps"])
async def deploy_app(request: Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return HTTPException(status_code=400, detail="Invalid JSON payload")

    if 'uri' in data:
        # Retrieve and process the application configuration from the URI
        uri = data['uri']
        print(f"The path URI received is {uri}")

        try:
            response = requests.get(uri)
            response.raise_for_status()
            yaml_data = response.text
            json_data = yaml.safe_load(yaml_data)
        except requests.RequestException as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch data from URI: {e}")
    else:
        # The YAML data is in the request
        json_data = data['yaml']

    validation_error = validate_yaml(json_data)

    if validation_error is None:
        try:
            app_id, components = get_yaml_info(json_data)

            if r.value_in_hash("system_app_hash", app_id):
                raise HTTPException(status_code=400,
                                    detail="Error: app_id already exists in the system")
            else:
                try:
                    r.push("valid_descriptions_queue", json.dumps(json_data))
                    r.update_dict_value('system_app_hash', app_id, "Queued")
                    r.add_components(app_id, components)
                except:
                    raise HTTPException(status_code=400,
                                        detail="Error pushing to the queue")
        except Exception as e:
            print(f"Error checking the app in Redis: {e}")
            raise e

    else:
        raise HTTPException(status_code=400, detail=validation_error)


"----------------------------------------------------------------------------------------"
"            LIST ALL APPS                                                              "
"----------------------------------------------------------------------------------------"


@router.get("/list_all/", tags=["Apps"])
async def list_all():
    """
    Endpoint to return the current Redis dictionary values.
    """
    try:
        # Assuming r.get_dict() fetches the entire dictionary
        redis_data = r.get_dict(r.dict_name)
        if redis_data is None:
            return {"status": "No data in the system."}
        return {"System_status": redis_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving system status: {e}")


"----------------------------------------------------------------------------------------"
"            APP STATUS                                                                 "
"----------------------------------------------------------------------------------------"


@router.get("/status/{app_id}", tags=["Apps"])
async def get_app_status(app_id: str):
    """
    Endpoint to check the status of a specific application based on its app_id.

    Args:
        app_id (str): The application ID to look up in Redis.

    Returns:
        dict: The status of the application, or an error message if not found.
    """
    try:
        # Fetch the value of the given app_id from Redis
        app_status = r.get_dict_value('system_app_hash', app_id)
        print(app_status)
        if app_status is None:
            # If the app_id doesn't exist in Redis, return a 404 error
            raise HTTPException(status_code=404, detail=f"App ID '{app_id}' not found in the system.")

        # Return the app status
        return {"app_id": app_id, "status": app_status}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving status for app_id '{app_id}': {e}")


"----------------------------------------------------------------------------------------"
"            APP DETAILS                                                                "
"----------------------------------------------------------------------------------------"


@router.get("/apps/details/{app_id}", tags=["Apps"])
async def get_app_details(app_id: str):
    """
    Returns the details of an application, including its components and the status of pods in Karmada.
    """



    try:
        # Get the application state
        app_state = r.get_dict_value(r.dict_name, app_id)
        if not app_state:
            raise Exception(f"Application '{app_id}' not found.")

        # Get the components of the application
        components = r.get_components(app_id)
        if not components:
            raise Exception(f"No components found for application '{app_id}'.")

        print(components)
        print("--------------------")
        pods_info = get_contexts_and_pods()
        print(pods_info)

        component_details = []
        for component in components:
            details = r.get_component_details(component)

            # Filter pods that match the component name (as a substring)
            related_pods = [
                pod for pod in pods_info
                if "pod_name" in pod and component in pod["pod_name"]
            ]

            details["pods"] = related_pods if related_pods else "No matching pods found."
            component_details.append({
                "name": component,
                "details": details
            })

        # Build the response
        app_details = {
            "app_id": app_id,
            "state": app_state,
            "components": component_details
        }

        return app_details

    except Exception as e:
        return {"error": f"Error retrieving application details: {str(e)}"}



"----------------------------------------------------------------------------------------"
"            APP PERFORMANCE                                                            "
"----------------------------------------------------------------------------------------"


@router.get("/performance/{app_id}", tags=["Apps"])
async def get_app_performance(app_id: str):
    print("Returning the app mQoS metric for", app_id)
    return (json.dumps(app_id))


"----------------------------------------------------------------------------------------"
"            REMOVE APP                                                                 "
"----------------------------------------------------------------------------------------"


@router.delete("/remove/{app_id}", tags=["Apps"])
async def update_app_status(app_id: str):
    """
    Endpoint to update the status of an application to 'removed' based on its app_id.

    Args:
        app_id (str): The application ID to look up in Redis.

    Returns:
        dict: A success message if the application was updated to 'removed',
              or an error message if the app_id was not found.
    """
    try:
        # Check if the app_id exists in the Redis dictionary
        app_status = r.get_dict_value('system_app_hash', app_id)

        if app_status is None:
            # If the app_id doesn't exist, return a 404 error
            raise HTTPException(status_code=404, detail=f"App ID '{app_id}' not found in the system.")

        # If the app_id exists, update the status to 'removed'
        r.update_dict_value('system_app_hash', app_id, "To_be_removed")
        json_data = {"MLSysOpsApplication": {"name": app_id}}
        r.push('valid_descriptions_queue', json.dumps(json_data))
        return {"app_id": app_id, "message": "Application status updated to 'To_be_removed'."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating status for app_id '{app_id}': {e}")

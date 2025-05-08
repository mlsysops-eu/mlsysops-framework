import json
import subprocess
from pydantic import BaseModel
import requests
import yaml
from fastapi import APIRouter, HTTPException, Request, Body
from jsonschema import validate, ValidationError
from typing import List, Optional
from pydantic import BaseModel, Field
from MLSysOps_Schemas.mlsysops_schemas import app_schema
from redis_setup import redis_mgt as rm

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

# JSON schema with enum validation for the city
# Update the required fields in the JSON schema
schema = app_schema

import os

# os.environ["LOCAL_OTEL_ENDPOINT"] = "http://172.25.27.228:9999/metrics"
# os.environ["TELEMETRY_ENDPOINT"] = "172.25.27.228:4317"

os.environ["LOCAL_OTEL_ENDPOINT"] = "http://172.25.27.4:9464/metrics"
os.environ["TELEMETRY_ENDPOINT"] = "172.25.27.4:4317"

karmada_api_kubeconfig = "/home/runner/karmada_management/karmada-api.kubeconfig"
uth_dev_kubeconfig = "/home/runner/karmada_management/uth-dev.kubeconfig"
uth_prod_kubeconfig = "/home/runner/karmada_management/uth-prod.kubeconfig"
# List of kubeconfig files to check
kubeconfigs = [
    os.getenv("KARMADA_KUBECONFIG", "/root/.kube/karmada-api.kubeconfig"),
    os.getenv("UTH_DEV_KUBECONFIG", "/root/.kube/uth-dev.kubeconfig"),
    os.getenv("UTH_PROD_KUBECONFIG", "/root/.kube/uth-prod.kubeconfig"),
]


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
                        pod_details.append({
                            "error": f"Error fetching pods for context {context_name} ({kubeconfig}): {pod_result.stderr.strip()}"})
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
                    pod_details.append(
                        {"error": f"Error while listing pods for context {context_name} ({kubeconfig}): {str(e)}"})

        except Exception as e:
            pod_details.append({"error": f"Error while retrieving contexts from {kubeconfig}: {str(e)}"})

    return pod_details


def store_qos_metrics(app_id, app_description):
    """
    Parses the application description and stores QoS metrics in Redis.

    :param app_id: The unique identifier of the application.
    :param app_description: JSON application description.
    """
    try:
        # Extract components
        components = app_description.get("MLSysOpsApplication", {}).get("components", [])

        for component in components:
            component_data = component.get("Component", {})
            component_name = component_data.get("name")

            if not component_name:
                continue  # Skip if component name is missing

            qos_metrics = component.get("QoS-Metrics", [])

            if not qos_metrics:
                continue  # Skip if no QoS metrics are found

            redis_key = f"{app_id}:{component_name}"

            # Store QoS metrics in a Redis hash
            for metric in qos_metrics:
                metric_id = metric.get("ApplicationMetricID")
                r.update_dict_value("component_metrics", redis_key, metric_id)

    except:
        print(f"Error updating metrics in redis : ")


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

# Define Pydantic Model for Validation
class ComponentModel(BaseModel):
    Component: Dict[str, Any]
    externalAccess: Optional[bool] = None
    nodePlacement: Optional[Dict[str, Any]] = None
    restartPolicy: Optional[str] = None
    containers: Optional[List[Dict[str, Any]]] = None

class MLSysOpsApplicationModel(BaseModel):
    name: str = Field(..., title="Application Name")
    clusterPlacement: Optional[Dict[str, Any]] = None
    components: Optional[List[ComponentModel]] = None

class RootModel(BaseModel):
    MLSysOpsApplication: MLSysOpsApplicationModel

"----------------------------------------------------------------------------------------"
"            DEPLOY APP                                                                  "
"----------------------------------------------------------------------------------------"
@router.post("/deploy", tags=["Applications"])
async def deploy_app(payload: RootModel):
    try:
        # Convert Pydantic object to dict
        parsed_data = payload.dict(by_alias=True)

        validation_error = validate_yaml(parsed_data)

        # Extract app_id and components
        app_id, components = get_yaml_info(parsed_data)

        # Check if app_id already exists in Redis
        if r.value_in_hash("system_app_hash", app_id):
            raise HTTPException(status_code=400, detail="Error: app_id already exists in the system")

        try:
            # Store in Redis
            r.push("valid_descriptions_queue", json.dumps(parsed_data))
            r.update_dict_value('system_app_hash', app_id, "Queued")
            r.add_components(app_id, components)
            store_qos_metrics(app_id, parsed_data)

            return {"app_id": app_id, "status": "Queued successfully"}

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error updating the info in Redis: {str(e)}")

    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unexpected error: {str(e)}")

"----------------------------------------------------------------------------------------"
"            LIST ALL APPS                                                              "
"----------------------------------------------------------------------------------------"


@router.get("/list_all/", tags=["Applications"])
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


@router.get("/status/{app_id}", tags=["Applications"])
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


@router.get("/apps/details/{app_id}", tags=["Applications"])
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
        pods_info = get_pods_from_kubeconfigs()
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


@router.get("/performance/{app_id}", tags=["Applications"])
async def get_app_performance(app_id: str):
    """
    Retrieves performance metrics for a given app_id from the 'component_metrics' hash.

    :param app_id: The application ID to filter metrics.
    :return: A list of tuples [(metric_name, metric_value), ...]
    """
    print("Returning the app mQoS metric for", app_id)

    if not r.redis_conn:
        return {"error": "Redis connection not established"}

    try:
        #  Get all keys from the hash "component_metrics"
        hash_keys = r.redis_conn.hkeys("component_metrics")

        #  Filter keys that contain the app_id
        metric_keys = [key.decode("utf-8") for key in hash_keys if app_id in key.decode("utf-8")]

        if not metric_keys:
            return {"message": f"No metrics found for app_id '{app_id}'"}

        # Get metric values from Redis
        metric_values = r.redis_conn.hmget("component_metrics", metric_keys)

        # Execute `mlsTelemetryClient.get_metric_value_with_label` for each metric
        results = []
        for metric_key, metric_value in zip(metric_keys, metric_values):
            if metric_value:
                metric_name = metric_value.decode("utf-8")  # Decode Redis stored value
                metric_name = str(metric_name).lower()
                print(metric_name)

        return results  # Returns a list of tuples [(metric_name, metric_value), ...]

    except Exception as e:
        return {"error": f"Error retrieving performance metrics: {e}"}


"----------------------------------------------------------------------------------------"
"            REMOVE APP                                                                 "
"----------------------------------------------------------------------------------------"


@router.delete("/remove/{app_id}", tags=["Applications"])
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
        r.delete_component(app_id)
        r.delete_app_components_from_hash("component_metrics", app_id)
        json_data = {"MLSysOpsApplication": {"name": app_id}}
        r.push('valid_descriptions_queue', json.dumps(json_data))
        return {"app_id": app_id, "message": "Application status updated to 'To_be_removed'."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating status for app_id '{app_id}': {e}")

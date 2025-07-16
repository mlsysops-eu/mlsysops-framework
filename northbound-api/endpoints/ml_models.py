from datetime import datetime

import yaml
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
import json
from redis_setup import redis_mgt as rm
from jsonschema import validate, ValidationError
import requests
from MLSysOps_Schemas.mlsysops_schemas import app_schema
import os
import subprocess
from kubernetes import client, utils, config
from kubernetes.utils.create_from_yaml import FailToCreateError
from kubernetes.client.rest import ApiException

from typing import Annotated, List, Optional, Dict, Any
from pydantic import BaseModel, Field

# JSON schema with enum validation for the city
schema = app_schema

os.environ["LOCAL_OTEL_ENDPOINT"] = "http://172.25.27.4:9464/metrics"
os.environ["TELEMETRY_ENDPOINT"] = "172.25.27.4:4317"

karmada_api_kubeconfig = "/home/runner/karmada_management/karmada-api.kubeconfig"
uth_dev_kubeconfig = "/home/runner/karmada_management/uth-dev.kubeconfig"
uth_prod_kubeconfig = "/home/runner/karmada_management/uth-prod.kubeconfig"
kubeconfigs = [
    os.getenv("KARMADA_KUBECONFIG", "/root/.kube/karmada-api.kubeconfig"),
    os.getenv("UTH_DEV_KUBECONFIG", "/root/.kube/uth-dev.kubeconfig"),
    os.getenv("UTH_PROD_KUBECONFIG", "/root/.kube/uth-prod.kubeconfig"),
]


# Define Pydantic Model for Validation using v2 syntax
class ComponentModel(BaseModel):
    Component: Dict[str, Any]
    externalAccess: Optional[bool] = None
    nodePlacement: Optional[Dict[str, Any]] = None
    restartPolicy: Optional[str] = None
    containers: Optional[Annotated[List[Dict[str, Any]], Field(min_items=1)]] = None


class MLSysOpsApplicationModel(BaseModel):
    name: str = Field(..., title="Application Name")
    mlsysops_id: str = Field(..., alias="mlsysops-id", title="MLSysOps ID")
    clusterPlacement: Optional[Dict[str, Any]] = None
    components: Annotated[List[ComponentModel], Field(min_items=1)]


class RootModel(BaseModel):
    MLSysOpsApplication: MLSysOpsApplicationModel


class RootModel(BaseModel):
    MLSysOpsApplication: MLSysOpsApplicationModel


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


def remove_none_fields(data):
    if isinstance(data, dict):
        return {
            k: remove_none_fields(v)
            for k, v in data.items()
            if v is not None
        }
    elif isinstance(data, list):
        return [remove_none_fields(item) for item in data if item is not None]
    else:
        return data


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
"            DEPLOY ML MODEL                                                              "
"----------------------------------------------------------------------------------------"


@router.post("/deploy_ml", tags=["ML-models"])
async def deploy_ml(payload: RootModel):
    # Convert Pydantic object to dict

    parsed_data = payload.dict(by_alias=True)
    parsed_data = remove_none_fields(parsed_data)

    # Validate YAML structure
    validation_error = validate_yaml(parsed_data)

    try:
        internal_uid = parsed_data["MLSysOpsApplication"]["mlsysops-id"]
    except KeyError:
        print("The mlsysops-id is not specified in the model description")

    if validation_error is None and internal_uid != "0":

        try:
            r.push("ml_deployment_queue", json.dumps(parsed_data))
            timestamp = datetime.now()
            info = {
                'status': 'pending',
                'timestamp': str(timestamp)
            }
            r.update_dict_value('endpoint_hash', internal_uid, str(info))
            return {"status": "success", "message": "Deployment request added to queue"}
        except Exception as e:
            print(f"Error checking the app in Redis: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail=validation_error)


"----------------------------------------------------------------------------------------"
"            LIST ALL APPS                                                              "
"----------------------------------------------------------------------------------------"


@router.get("/list_all/", tags=["ML-models"])
async def list_all():
    """
    Endpoint to return the current Redis dictionary values.
    """
    try:
        redis_data = r.get_dict('endpoint_hash')
        if redis_data is None:
            return {"status": "No data in the system."}
        return {"System_status": redis_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving ml model status: {e}")


"----------------------------------------------------------------------------------------"
"           ML DEPLOYMENT STATUS                                                                 "
"----------------------------------------------------------------------------------------"


@router.get("/status/{model_uid}", tags=["ML-models"])
async def get_ml_status(model_uid: str):
    """
    Endpoint to check the status of a specific application based on its app_id.

    Args:
        app_id (str): The application ID to look up in Redis.

    Returns:
        dict: The status of the application, or an error message if not found.
    """
    try:
        # Fetch the value of the given app_id from Redis
        app_status = r.get_dict_value('endpoint_hash', model_uid)
        print(app_status)
        if app_status is None:
            # If the app_id doesn't exist in Redis, return a 404 error
            raise HTTPException(status_code=404, detail=f"Model ID '{model_uid}' not found in the system.")

        # Return the app status
        return {"Model ": model_uid, "status": app_status}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving status for app_id '{model_uid}': {e}")


"----------------------------------------------------------------------------------------"
"            REMOVE APP                                                                 "
"----------------------------------------------------------------------------------------"


@router.delete("/remove/{model_uid}", tags=["ML-models"])
async def remove_ml_model(model_uid: str):
    """
    Endpoint to update the status of an application to 'removed' based on its app_id.

    Args:
        app_id (str): The application ID to look up in Redis.

    Returns:
        dict: A success message if the application was updated to 'removed',
              or an error message if the app_id was not found.
              :param model_uid:
    """
    try:
        # Check if the app_id exists in the Redis dictionary
        app_status = r.get_dict_value('endpoint_hash', model_uid)

        if app_status is None:
            # If the app_id doesn't exist, return a 404 error
            raise HTTPException(status_code=404, detail=f"App ID '{model_uid}' not found in the system.")

        # If the app_id exists, update the status to 'removed'
        r.update_dict_value('endpoint_hash', model_uid, "To_be_removed")
        delete_msg = str({model_uid: "delete"})
        r.push("ml_deployment_queue", delete_msg)
        return {"model_uid": model_uid, "message": "Application status updated to 'To_be_removed'."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating status for app_id '{model_uid}': {e}")

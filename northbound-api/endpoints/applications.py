# endpoints/applications.py
import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime
from kubernetes import client, config
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from kubernetes.client import ApiException

from MLSysOps_Schemas.mlsysops_model import MlsysopsappSchema, Component
from redis_setup import redis_mgt as rm  # Your RedisManager class

router = APIRouter()
logger = logging.getLogger(__name__)

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


def get_pod_info(comp_name, model_id, api_client):
    """Query Karmada proxy API to find the pod with the given component name."""
    path = "/apis/search.karmada.io/v1alpha1/proxying/karmada/proxy/api/v1/namespaces/default/pods"
    try:
        response = api_client.call_api(
            resource_path=path, method="GET", auth_settings=["BearerToken"],
            response_type="json", _preload_content=False
        )
        pods = json.loads(response[0].data.decode("utf-8"))
        print(pods)

    except ApiException as exc:
        logger.error(f"Failed to fetch pods: {exc}")
        return None, None, None
    return None, None, None

def get_node_ip(host, api_client):
    """Query from Karmada proxy API to get the IP address of the given node."""
    nodes = get_k8s_nodes(api_client)
    node_ip = None

    for node in nodes:
        if node["metadata"]["name"] == host:
            internal_ip = None
            external_ip = None

            for address in node["status"]["addresses"]:
                if address["type"] == "ExternalIP":
                    external_ip = address["address"]
                    logger.debug(f"Node: {host}, External IP: {external_ip}")
                elif address["type"] == "InternalIP":
                    internal_ip = address["address"]
                    logger.debug(f"Node: {host}, Internal IP: {internal_ip}")

            # Decide which IP to use
            node_ip = external_ip if external_ip else internal_ip
            break

    if not node_ip:
        logger.error(f"Failed to resolve IP for node: {host}")
    return node_ip


def get_k8s_nodes(api_client):
    """Query Karmada proxy API for the list of nodes."""
    path = "/apis/search.karmada.io/v1alpha1/proxying/karmada/proxy/api/v1/nodes"
    try:
        response = api_client.call_api(
            resource_path=path, method="GET", auth_settings=["BearerToken"], response_type="json", _preload_content=False
        )
        nodes = json.loads(response[0].data.decode("utf-8"))
        return nodes.get("items", [])
    except ApiException as exc:
        logger.error(f"Failed to fetch nodes: {exc}")
        return []


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


def store_qos_metrics(request:Request,app_id, app_description):
    """
    Parses the application description and stores QoS metrics in Redis.

    :param app_id: The unique identifier of the application.
    :param app_description: JSON application description.
    """
    redis_mgr: rm.RedisManager = request.app.state.redis
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
                redis_mgr.update_dict_value("component_metrics", redis_key, metric_id)

    except:
        print(f"Error updating metrics in redis : ")


async def check_deployment_status(comp_name,app_id):
    logger.debug("Checking deployment for Application ...")

    # Load Karmada kubeconfig and create Kubernetes API client
    karmada_api_kubeconfig = os.getenv("KARMADA_API_KUBECONFIG", "kubeconfigs/karmada-api.kubeconfig")
    try:
        config.load_kube_config(config_file=karmada_api_kubeconfig)
        api_client = client.ApiClient()
    except Exception as e:
        logger.error(f"Failed to load Karmada kubeconfig: {e}")
        return

    while True:
        pod_name, host, app_id = get_pod_info(comp_name, app_id, api_client)

        if not pod_name:
            logger.debug(f"Failed to find running pod for comp_name: {comp_name}, retrying in 5 seconds...")
            await asyncio.sleep(5)
        else:
            logger.debug(f"Found pod: {pod_name} running on host: {host}")
            break

    svc_path = f"/apis/search.karmada.io/v1alpha1/proxying/karmada/proxy/api/v1/namespaces/default/services/{comp_name}"
    logger.debug(f"Fetching service details from Karmada proxy API: {svc_path}")
    try:
        response = api_client.call_api(
            resource_path=svc_path, method="GET", auth_settings=["BearerToken"], response_type="json",
            _preload_content=False
        )
        svc_obj = json.loads(response[0].data.decode("utf-8"))
    except ApiException as exc:
        logger.error(f"Failed to fetch service: {exc}")
        return

    if not svc_obj:
        logger.error(f"Service not found for {comp_name}")
        return

    # Retrieve the assigned ClusterIP and port
    local_endpoint = svc_obj["spec"]["clusterIP"] + ":" + str(svc_obj["spec"]["ports"][0]["port"])
    global_endpoint_port = str(svc_obj["spec"]["ports"][0].get("nodePort", ""))

    # Prepare and store deployment details
    if app_id is not None:
        timestamp = datetime.now()
        info = {
            "status": "deployed",
            "timestamp": str(timestamp),
            "local_endpoint": local_endpoint,
        }

        # Get node IP and include global endpoint details if available
        node_ip = get_node_ip(host, api_client)
        if global_endpoint_port and node_ip:
            info["global_endpoint"] = f"{node_ip}:{global_endpoint_port}"

        logger.debug(f"Pushing endpoint details to Redis: {info}")

    await asyncio.sleep(2)


@router.post("/deploy", tags=["Applications"])
async def deploy_app(request: Request, payload: MlsysopsappSchema) -> Dict[str, Any]:
    """
    Deploy an application to Redis:
    - Serialize the incoming Pydantic model to JSON
    - Remove any None fields
    - Push the result onto a Redis list
    - Update a Redis hash to mark status = "Queued"
    """
    redis_mgr: rm.RedisManager = request.app.state.redis

    # 1) Convert Pydantic model ? dict, then strip out None values
    try:

        app_id = payload.MLSysOpsApp.name

        components: List[Component] = payload.MLSysOpsApp.components or []
        comp_names = [comp.metadata.name for comp in components]
        logger.debug("Deploying app_id=%s with components=%s", app_id, comp_names)
    except Exception as exc:
        logger.error("Error converting payload to dict: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload format: {exc}"
        )

    # 2) Check if the app_id already exists
    try:
        if redis_mgr.value_in_hash("system_app_hash", app_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Application '{app_id}' already exists"
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Redis lookup failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Redis lookup error: {exc}"
        )

    # 3) Serialize to JSON (converting Enums, etc.) and push to Redis
    try:
        encoded = jsonable_encoder(payload)
        encoded_clean = _remove_none_fields(encoded)
        payload_json = json.dumps(encoded_clean)

        redis_mgr.push("valid_descriptions_queue", payload_json)
        redis_mgr.update_dict_value("system_app_hash", app_id, "Queued")
        redis_mgr.update_dict_value("app_data_hash", app_id, payload_json)
        redis_mgr.add_components(app_id, comp_names)

    except Exception as exc:
        logger.error("Error storing application in Redis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Redis store error: {exc}"
        )

    return {"app_id": app_id, "status": "Queued successfully"}

"----------------------------------------------------------------------------------------"
"            LIST ALL APPS                                                              "
"----------------------------------------------------------------------------------------"


@router.get("/list_all/", tags=["Applications"])
async def list_all(request: Request):
    """
    Endpoint to return the current Redis dictionary values.
    """

    redis_mgr: rm.RedisManager = request.app.state.redis
    try:
        # Assuming r.get_dict() fetches the entire dictionary
        redis_data = redis_mgr.get_dict(redis_mgr.dict_name)
        if redis_data is None:
            return {"status": "No data in the system."}
        return {"System_status": redis_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving system status: {e}")


"----------------------------------------------------------------------------------------"
"            APP STATUS                                                                 "
"----------------------------------------------------------------------------------------"


@router.get("/status/{app_id}", tags=["Applications"])
async def get_app_status(request: Request,app_id: str):
    """
    Endpoint to check the status of a specific application based on its app_id.

    Args:
        app_id (str): The application ID to look up in Redis.

    Returns:
        dict: The status of the application, or an error message if not found.
        :param app_id:
        :param request:
    """
    redis_mgr: rm.RedisManager = request.app.state.redis
    try:
        # Fetch the value of the given app_id from Redis
        app_status = redis_mgr.get_dict_value('system_app_hash', app_id)
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
async def get_app_details(request: Request,app_id: str):
    """
    Returns the details of an application, including its components and the status of pods in Karmada.
    """
    redis_mgr: rm.RedisManager = request.app.state.redis
    try:
        # Get the application state
        app_state = redis_mgr.get_dict_value(redis_mgr.dict_name, app_id)
        if not app_state:
            raise Exception(f"Application '{app_id}' not found.")

        # Get the components of the application
        components = redis_mgr.get_components(app_id)
        if not components:
            raise Exception(f"No components found for application '{app_id}'.")

        print(components)
        print("--------------------")

        pods_info = get_pods_from_kubeconfigs()
        print(pods_info)

        component_details = []
        for component in components:
            check_deployment_status(components, app_id)


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
async def get_app_performance(request: Request,app_id: str):
    """
    Retrieves performance metrics for a given app_id from the 'component_metrics' hash.

    :param app_id: The application ID to filter metrics.
    :return: A list of tuples [(metric_name, metric_value), ...]
    """
    redis_mgr: rm.RedisManager = request.app.state.redis
    print("Returning the app mQoS metric for", app_id)

    if not redis_mgr.redis_conn:
        return {"error": "Redis connection not established"}

    try:
        #  Get all keys from the hash "component_metrics"
        hash_keys = redis_mgr.redis_conn.hkeys("component_metrics")

        #  Filter keys that contain the app_id
        metric_keys = [key.decode("utf-8") for key in hash_keys if app_id in key.decode("utf-8")]

        if not metric_keys:
            return {"message": f"No metrics found for app_id '{app_id}'"}

        # Get metric values from Redis
        metric_values = redis_mgr.redis_conn.hmget("component_metrics", metric_keys)

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
async def update_app_status(request: Request,app_id: str):
    """
    Endpoint to update the status of an application to 'removed' based on its app_id.

    Args:
        app_id (str): The application ID to look up in Redis.

    Returns:
        dict: A success message if the application was updated to 'removed',
              or an error message if the app_id was not found.
    """
    redis_mgr: rm.RedisManager = request.app.state.redis
    try:
        # Check if the app_id exists in the Redis dictionary
        app_status = redis_mgr.get_dict_value('system_app_hash', app_id)

        if app_status is None:
            # If the app_id doesn't exist, return a 404 error
            raise HTTPException(status_code=404, detail=f"App ID '{app_id}' not found in the system.")

        # If the app_id exists, update the status to 'removed'
        redis_mgr.update_dict_value('system_app_hash', app_id, "To_be_removed")
        redis_mgr.remove_key("app_data_hash", app_id)
        redis_mgr.delete_component(app_id)
        redis_mgr.delete_app_components_from_hash("component_metrics", app_id)
        json_data = {"MLSysOpsApp": {"name": app_id}}
        redis_mgr.push('valid_descriptions_queue', json.dumps(json_data))
        return {"app_id": app_id, "message": "Application status updated to 'To_be_removed'."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating status for app_id '{app_id}': {e}")



def _remove_none_fields(obj: Any) -> Any:
    """
    Recursively drop keys/values that are None in dicts or None items in lists.
    """
    if isinstance(obj, dict):
        return {k: _remove_none_fields(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_remove_none_fields(item) for item in obj if item is not None]
    return obj

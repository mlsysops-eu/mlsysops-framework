import json

import requests
import yaml
from fastapi import APIRouter, HTTPException, Request
from jsonschema import validate, ValidationError
from MLSysOps_Schemas.mlsysops_schemas import node_schema, cluster_schema, datacenter_schema, continuum_schema
from redis_setup import redis_mgt as rm
from agents.mlsysops.logger_util import logger

# JSON schema with enum validation for the city
# Update the required fields in the JSON schema

# Dictionary to map types to schemas
schema_map = {
    "MLSysOpsNode": node_schema,
    "MLSysOpsCluster": cluster_schema,
    "MLSysOpsDatacenter": datacenter_schema,
    "MLSysOpsContinuum": continuum_schema,
}


def validate_infrastructure_file(json_data):
    # Extract the type from the JSON datafirst_key = next(iter(data))
    infrastructure_type = next(iter(json_data), None)

    # Get the corresponding schema from the map
    schema = schema_map.get(infrastructure_type)

    if schema is None:
        return f"Invalid file type: {infrastructure_type}, please submit a valid infrastructure file."
    # Perform validation
    try:
        validate(instance=json_data, schema=schema)
        return None  # Validation passed
    except ValidationError as e:
        return f"Validation error for {infrastructure_type}: {e.message}"
    except Exception as e:
        return f"Error validating {infrastructure_type}: {str(e)}"


router = APIRouter()

# Connect to Redis using RedisManager
r = rm.RedisManager()
r.connect()

# Global variable to store the last connection time
last_connection_time = None

"----------------------------------------------------------------------------------------"
"            REGISTER INFRA                                                             "
"----------------------------------------------------------------------------------------"


@router.post("/register", tags=["Infra"])
async def deploy_infra(request: Request):
    try:
        data = await request.json()
        #logger(data)
    except json.JSONDecodeError:
        logger.error("error")
        return HTTPException(status_code=400, detail="Invalid JSON payload")

    if 'uri' in data:
        # Retrieve and process the application configuration from the URI
        uri = data['uri']
        logger.error(f"The path uri received is  {uri}")

        try:
            response = requests.get(uri)
            response.raise_for_status()
            yaml_data = response.text
            json_data = yaml.safe_load(yaml_data)
        except requests.RequestException as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch data from URI: {e}")
    else:
        # the yaml data are in the request
        json_data = data['yaml']

    validation_error = validate_infrastructure_file(json_data)

    if validation_error is None:
        logger.info("Now execute the validation with the actual infrastructure and save in a datastructure")

    else:
        raise HTTPException(status_code=400, detail=validation_error)


"----------------------------------------------------------------------------------------"
"            LIST INFRASTRUCTURE                                                        "
"----------------------------------------------------------------------------------------"


@router.get("/list/", tags=["Infra"])
async def list_infra(id_type: str, id_value: str):
    logger.info(f"requested info : {id_type}, with id {id_value}")





"----------------------------------------------------------------------------------------"
"           GET NODE SATE                                                                "
"----------------------------------------------------------------------------------------"


# POST a new product
@router.get("/node/{node_id}", tags=["Infra"])
async def get_node_state(app_id: str):
    logger.info("return the app mQoS metric of ", app_id)
    return (json.dumps(app_id))


#IMPLEMENT THE LOGIC TO RETURN THE APP METRICS:

"----------------------------------------------------------------------------------------"
"            GET CLUSTER SATE                                                            "
"----------------------------------------------------------------------------------------"


@router.get("/cluster/{clus_id}", tags=["Infra"])
async def get_cluster_state(app_id: str):
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


"----------------------------------------------------------------------------------------"
"            GET DATACENTER SATE                                                         "
"----------------------------------------------------------------------------------------"


@router.get("/datacenter/{dc_id}", tags=["Infra"])
async def get_dc_state(dc_id: str):
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
        app_status = r.get_dict_value('system_app_hash', dc_id)

        if app_status is None:
            # If the app_id doesn't exist, return a 404 error
            raise HTTPException(status_code=404, detail=f"App ID '{dc_id}' not found in the system.")

        # If the app_id exists, update the status to 'removed'
        r.update_dict_value('system_app_hash', dc_id, "To_be_removed")
        json_data = {"MLSysOpsApplication": {"name": dc_id}}
        r.push('valid_descriptions_queue', json.dumps(json_data))
        return {"app_id": dc_id, "message": "Application status updated to 'To_be_removed'."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating status for app_id '{dc_id}': {e}")


"----------------------------------------------------------------------------------------"
"            UNREGISTER INFRA                                                                  "
"----------------------------------------------------------------------------------------"


# POST a new product
@router.delete("/unregister/{app_id}", tags=["Infra"])
async def unregister_infra(app_id: str):
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

        if app_status is None:
            # If the app_id doesn't exist in Redis, return a 404 error
            raise HTTPException(status_code=404, detail=f"App ID '{app_id}' not found in the system.")

        # Return the app status
        return {"app_id": app_id, "status": app_status}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving status for app_id '{app_id}': {e}")

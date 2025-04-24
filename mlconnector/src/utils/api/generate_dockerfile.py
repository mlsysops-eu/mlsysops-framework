import os
import docker
import yaml
from dotenv import load_dotenv
import subprocess
import pickle
from pkg_resources import Requirement
from io import StringIO

from utils.manage_s3 import S3Manager

load_dotenv(verbose=True, override=True)


s3_manager = S3Manager(
    os.getenv("AWS_S3_BUCKET_DATA"),
    os.getenv("AWS_ACCESS_KEY_ID"),
    os.getenv("AWS_SECRET_ACCESS_KEY"),
    os.getenv("AWS_ACCESS_URL")
)


BASE_URL = os.getenv('SIDE_API_ENDPOINT')
if not BASE_URL:
    raise ValueError("SIDE_API_ENDPOINT is not set in the .env file")

# Build the full URL
url = f"{BASE_URL}/deployment/add/operation"

template = """#!/usr/bin/python3
# Author John Byabazaire

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import pandas as pd
import joblib
import os
import requests
import json
from pydantic import create_model
from io import BytesIO
import base64
import urllib.parse
from datetime import datetime, timezone

from mlstelemetry import MLSTelemetry

{schema_code}

with open(
        os.path.join(os.path.dirname(__file__), "endpoint_tags.json")
    ) as f:
    tags_metadata = f.read()

app = FastAPI(
     title="MLSysOps ML Integration API",
    description="Machine Learning for Autonomic System Operation in the Heterogeneous Edge-Cloud Continuum",
    version="1.0.1",
    openapi_tags=json.loads(tags_metadata)
)

mlsTelemetryClient = MLSTelemetry("side-api", "inference")

def get_single_explanation(model_id, data):
    XAI_ENDPOINT = "http://daistwo.ucd.ie:34567/explain_single"
    headers = {{
        "accept": "application/json",
        "Content-Type": "application/json"
    }}   
    payload = {{
        "model_id": model_id,
        "data": data,
        "simple_format": True,
        "full_data": False,
        "include_image": True,
        "train_model_if_not_exist": True
    }}
    try:
        response = requests.post(XAI_ENDPOINT, headers=headers, json=payload)
        if response.status_code == 200:
            try:
                json_response = response.json()
                return json_response
            except Exception as json_err:
                print("Error parsing JSON response:", json_err)
                return None
        else:
            print(f"Error: Received status code {{response.status_code}}. Response content: {{response.text}}")
            return None
    except Exception as err:
        print("Request error occurred:", err)
        return None


@app.post("/prediction", tags=["Prediction"])
async def make_prediction(request: DynamicSchema):
    data_source = {data_source}
    model_id = "{model_id}"
    owner = "{owner}"
    url = "{url}"
    headers = {{
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }}
    current_timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    try:
        loaded_model = joblib.load("{model}")
        print("Model loaded successfully!")
        if data_source == 0:
            data_dict = request.data.dict()
            df = pd.DataFrame([data_dict])
            result_pred = loaded_model.predict(df)
            data = {{
                "ownerid": owner,
                "deploymentid": "{deploymentid}",
                "modelid": model_id,
                "data": str(data_dict),
                "result": str(result_pred),
                "timestamp": current_timestamp
            }}
            response = requests.post(url, headers=headers, json=data)
            print(f"Status Code: {{response.status_code}}")
            try:
                print("Response JSON:", response.json())
            except ValueError:
                print("No JSON response returned.")
            #if request.explanation:
            #    explanation_res = get_single_explanation(model_id,data_dict)
            #    if explanation_res:
            #        return {{"inference": str(result_pred), "explanation":explanation_res}}
            #    else:
            #        return {{"inference": str(result_pred), "explanation":"explanation_error"}}
            #else:
            return {{"inference": str(result_pred)}}
        else:
            return {{"url": request.data_link}}
    except Exception as e:
        return {{"error": f"Failed to load model: {{str(e)}}"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port={port})
"""
def prepare_model_artifact(s3_manager: S3Manager, model_name: str, download_dir: str = "/code/utils/api"):
    """
    Download the model from S3 into download_dir.
    Returns the local path to the downloaded model.
    """
    local_path = os.path.join(download_dir, model_name)
    # ensure the directory exists
    os.makedirs(download_dir, exist_ok=True)

    # download from S3
    s3_manager.download_file(object_name=model_name, download_path=local_path)
    print(f"Model downloaded to {local_path}")
    return local_path

def merge_requirements_from_dir(req_dir: str) -> list[str]:
    """
    Scan a directory for *.txt files, merge all requirements,
    dedupe, normalize, and return a sorted list.
    """
    all_reqs: set[str] = set()
    for fname in os.listdir(req_dir):
        if not fname.endswith('.txt'):
            continue
        path = os.path.join(req_dir, fname)
        with open(path, 'r') as f:
            content = f.read()
        all_reqs |= parse_requirements_content(content)

    return sorted(all_reqs, key=lambda r: r.lower())

def parse_requirements_content(content: str) -> set[str]:
    """Parse a requirements.txt content string into a normalized set of requirements."""
    reqs = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            req = Requirement.parse(line)
            extras = f"[{','.join(req.extras)}]" if req.extras else ""
            spec = ''.join(str(s) for s in req.specifier)
            reqs.add(f"{req.name}{extras}{spec}")
        except Exception:
            # fallback if pkg_resources can't parse
            reqs.add(line)
    return reqs

def generate_dockerfile(model_id):
    # generate a combined requirements.txt file
    model_reqs = prepare_model_artifact(s3_manager,  f"{model_id}.txt")
    
    reqs_dir = "/code/utils/api"
    merged = merge_requirements_from_dir(reqs_dir)

    req_path = "/code/utils/api/requirements.txt"
    os.makedirs(os.path.dirname(req_path), exist_ok=True)
    with open(req_path, "w") as f:
        for line in merged:
            f.write(line + "\n")
    req_path = "/code/utils/api/requirements.txt"
    os.makedirs(os.path.dirname(req_path), exist_ok=True)
    with open(req_path, "w") as f:
        for line in merged:
            f.write(line + "\n")

    dockerfile_content = f"""\
        FROM python:3.11

        WORKDIR /app

        COPY requirements.txt .
        
        RUN apt-get update && apt-get install -y build-essential
        
        RUN pip install --no-cache-dir -r requirements.txt

        RUN apt-get update && apt-get install -y curl
        # RUN curl -L -o model_name model_url
        COPY  . .

        EXPOSE 8000

        CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
        """
    with open("/code/utils/api/Dockerfile", "w") as file:
        file.write(dockerfile_content)
    print("Dockerfile generated successfully!")



def build_and_push_image(model, registry_url, image_name, registry_username, registry_password, inference_data, datasource, model_id,model_owner, deploymentid):
    params = {
        #"model_filename": model_name,
        "port": 8000,
        "schema_code":inference_data,
        "data_source":datasource,
        "model_id":model_id,
        "model":model,
        "owner":model_owner,
        "url":url,
        "deploymentid":deploymentid
    }
    generated_code = template.format(**params)

    with open("/code/utils/api/main.py", "w") as f:
        f.write(generated_code)

    print("Python file 'main.py' has been created with the provided parameters.")

    generate_dockerfile(model_id)
    client = docker.from_env()

    try:
        print("Building Docker image...")
        image, build_logs = client.images.build(path="/code/utils/api/", tag=image_name)
        for log in build_logs:
            print(log.get("stream", "").strip())
    except docker.errors.BuildError as e:
        print(f"Error building image: {e}")
        return

    print("Pushing Docker image...")
    #registry_url, image_tag = image_name.split("/", 1)
    client.login(username=registry_username, password=registry_password, registry=registry_url)

    try:
        push_logs = client.images.push(image_name, stream=True, decode=True)
        for log in push_logs:
            print(log)
    except docker.errors.APIError as e:
        print(f"Error pushing image: {e}")


"""def generate_json(deployment_id: str, image: str, placement, port: int = 8000):
    app = {
        "MLSysOpsApplication": {
            "name": "ml-app-1",
            "mlsysops-id": deployment_id
        }
    }

    # clusterPlacement if clusterID present
    if placement.get("clusterID") != "":
        app["MLSysOpsApplication"]["clusterPlacement"] = {
            "clusterID": [placement["clusterID"]],
            "instances": 1
        }

    # component definition
    comp = {
        "name": "ml-comp",
        "uid": deployment_id,
        "restartPolicy": "OnFailure",
        "containers": [
            {
                "image": image,
                "imagePullPolicy": "IfNotPresent",
                "ports": [{"containerPort": port}]
            }
        ]
    }

    # nodePlacement / continuumLayer
    node_placement = {}
    if placement.get("continuum") is not False:
        node_placement["continuumLayer"] = ["*"]
    elif placement.get("node") != "":
        node_placement["node"] = placement["node"]

    if node_placement:
        comp["nodePlacement"] = node_placement

    # attach component
    app["MLSysOpsApplication"]["components"] = [{"Component": comp}]
    return app"""

def generate_json(
    deployment_id: str,
    image: str,
    placement: dict,
    app_name: str = "ml-app-1",
    port: int = 8000
):
    app = {
        "MLSysOpsApplication": {
            "name": app_name,
            "mlsysops-id": deployment_id
        }
    }

    # Only add clusterPlacement if clusterID is not a wildcard
    cluster_id = placement.get("clusterID", "")
    if cluster_id and cluster_id != "*":
        app["MLSysOpsApplication"]["clusterPlacement"] = {
            "clusterID": [cluster_id],
            "instances": 1
        }

    # Build the component block
    component = {
        "Component": {
            "name": "ml-comp",
            "uid": deployment_id
        }
    }

    # Always consider continuumLayer, but only add node if it's not "*"
    node_conf = {}
    node_name = placement.get("node", "")
    if node_name and node_name != "*":
        node_conf["node"] = node_name

    continuum = placement.get("continuum", "")
    if continuum:
        node_conf["continuumLayer"] = [continuum]

    if node_conf:
        component["nodePlacement"] = node_conf

    # Add the remaining fields
    component["restartPolicy"] = "OnFailure"
    component["containers"] = [
        {
            "image": image,
            "imagePullPolicy": "IfNotPresent",
            "ports": [
                {"containerPort": port}
            ]
        }
    ]

    app["MLSysOpsApplication"]["components"] = [component]
    return app


def generate_yaml(
        deployment_id: str, 
        image: str,
        clusterID: str = None,
        node: str = None, 
        continuum: bool = False,
    ):
    yaml_content = {
        "apiVersion": "fractus.gr/v1",
        "kind": "MLSysOpsApp",
        "metadata": {
            "name": "ml-application"
        },
        "components": [
            {
                "Component": {
                    "name": "ml-comp",
                    "uid": deployment_id
                },
                "placement": {},
                "restartPolicy": "OnFailure",
                "containers": [
                    {
                        "image": image,
                        "imagePullPolicy": "IfNotPresent",
                        "ports": [
                            {
                                "containerPort": 8000
                            }
                        ]
                    }
                ]
            }
        ]
    }
    
    placement = {}
    if continuum:
        placement["continuum"] = ["*"]
    else:
        if clusterID:
            placement["clusterID"] = clusterID
        if node:
            placement["node"] = node

    if placement:
        yaml_content["components"][0]["placement"] = placement
    
    return yaml_content

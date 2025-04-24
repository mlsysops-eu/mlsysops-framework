import os
import docker
import yaml
import requests


def generate_entry_file(file_list):
    script_template = f"""#!/bin/bash
    set -e
    echo "Running {file_list[1]} with {file_list[0]}"
    python {file_list[1]} {file_list[0]}
    echo "Saving model"
    python save_model.py
    """

    with open("/code/utils/train/entrypoint.sh", "w") as f:
        f.write(script_template)


    os.chmod("/code/utils/train/entrypoint.sh", 0o755)

template = """#!/usr/bin/python3
# Author John Byabazaire

import pandas as pd
import joblib
import os
import json
import requests
from io import BytesIO
import base64
import urllib.parse
from dotenv import load_dotenv
from requests.exceptions import RequestException, HTTPError

load_dotenv()

import os
import requests
import mimetypes

def upload_model_file(file_path: str,file_kind: str,model_id: str) -> dict:
    BASE_URL = os.getenv('SIDE_API_ENDPOINT')
    if not BASE_URL:
        raise ValueError("SIDE_API_ENDPOINT is not set in the .env file")
    url = f"{{BASE_URL}}/model/{{model_id}}/upload"
    filename = os.path.basename(file_path)

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"No such file: {{file_path}}")

    # get MIME type based on extension
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    try:
        with open(file_path, "rb") as f:
            files = {{
                "file": (filename, f, mime_type),
            }}
            data = {{"file_kind": file_kind}}
            headers = {{"Accept": "application/json"}}

            resp = requests.post(url, headers=headers, files=files, data=data)
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {{"status": "success", "response_text": resp.text}}

    except HTTPError as http_err:
        # The server returned an HTTP error code
        raise HTTPError(
            f"HTTP error uploading {{filename}}: {{http_err}} - "
            f"Response body: {{http_err.response.text}}"
        ) from http_err

    except RequestException as req_err:
        # Network-level errors (connection timeout, DNS failure, etc.)
        raise RequestException(f"Network error during upload: {{req_err}}") from req_err


# Example usage:
if __name__ == "__main__":
    result = upload_model_file(
        file_path="{file_name}",
        file_kind="model",
        model_id="{model_id}"
    )
    print("Upload response:", result)
"""

def generate_dockerfile():
    dockerfile_content = f"""\
        FROM python:3.9-slim

        RUN apt-get update && apt-get install -y curl git jq && rm -rf /var/lib/apt/lists/*

        WORKDIR /app
        
        COPY requirements.txt .
        
        RUN apt-get update && apt-get install -y build-essential
        
        RUN pip install --no-cache-dir -r requirements.txt

        COPY . /app

        # Set the entrypoint.
        ENTRYPOINT ["/app/entrypoint.sh"]
        """
    with open("/code/utils/train/Dockerfile", "w") as file:
        file.write(dockerfile_content)
    print("Dockerfile generated successfully!")


def build_and_push_image(modelid, registry_url, image_name, registry_username, registry_password, training_data, training_code):
    file_list=[training_data, training_code]
    generate_entry_file(file_list)
    params = {
        "model_id": modelid,
        "file_name": modelid+".pkl",
    }
    generated_code = template.format(**params)

    with open("/code/utils/train/save_model.py", "w") as f:
        f.write(generated_code)
    generate_dockerfile()
    client = docker.from_env()

    try:
        print("Building Docker image...")
        image, build_logs = client.images.build(path="/code/utils/train/", tag=image_name)
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
    cluster_id = placement.get("clusterID", "")
    if cluster_id:
        app["MLSysOpsApplication"]["clusterPlacement"] = {
            "clusterID": [cluster_id],
            "instances": 1
        }
    component = {
        "Component": {
            "name": "ml-comp",
            "uid": deployment_id
        }
    }
    node_conf = {}
    node_name = placement.get("node", "")
    if node_name:
        node_conf["node"] = node_name
    elif placement.get("continuum", False):
        node_conf["continuumLayer"] = ["*"]

    if node_conf:
        component["nodePlacement"] = node_conf

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

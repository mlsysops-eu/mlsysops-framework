import os
import docker
import yaml
import requests


def generate_entry_file(file_list):
    file_paths_str = " ".join(f'"{fp}"' for fp in file_list)
    script_template = f"""#!/bin/bash
    set -e

    project_path="side-api/ml_models"
    file_paths=({file_paths_str})
    ref="main"
    VAL=""

    # URL-encode the project_path once.
    encoded_project=$(python3 -c "import urllib.parse; print(urllib.parse.quote_plus('$project_path'))")

    for file in "${{file_paths[@]}}"; do
        # URL-encode the file name. The inner '$file' refers to the bash variable.
        encoded_file=$(python3 -c "import urllib.parse; print(urllib.parse.quote_plus('$file'))")
        
        # Construct the GitLab API URL for this file.
        api_url="https://mlsysops-gitlab.e-ce.uth.gr/api/v4/projects/${{encoded_project}}/repository/files/${{encoded_file}}?ref=${{ref}}"
        echo "Constructed API URL for ${{file}}: $api_url"
        
        # Download the file metadata using the token.
        response=$(curl -sSL -H "VAL: $VAL" "$api_url")
        
        # Extract the 'content' field using jq.
        content=$(echo "$response" | jq -r '.content')
        
        if [ "$content" == "null" ]; then
            echo "Error: Failed to get file content for ${{file}} from API."
            echo "Response was: $response"
            exit 1
        fi
        
        # Decode the Base64 content and save it as the file.
        echo "$content" | base64 -d > "$file"
        echo "Downloaded and decoded file saved as ${{file}}"
    done
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

model_id ="{model_id}"
VAL = ""

def get_model_data(model_id):
    base_url = "http://daistwo.ucd.ie/model/get/"
    url = f"{{base_url}}{{model_id}}"
    headers = {{"accept": "application/json"}}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            try:
                return response.json()
            except Exception as e:
                return f"Error parsing JSON: {{e}}"
        else:
            return f"Error: Received status code {{response.status_code}}. Response: {{response.text}}"
    except Exception as err:
        return f"Request error occurred: {{err}}"

model = get_model_data(model_id)

project_path = "side-api/ml_models"
file_path = model["trained_model"][0]["modelname"] 
ref = "main"
VAL = ""


encoded_project = urllib.parse.quote_plus(project_path)
encoded_file = urllib.parse.quote_plus(file_path)

api_url = f"https://mlsysops-gitlab.e-ce.uth.gr/api/v4/projects/{{encoded_project}}/repository/files/{{encoded_file}}"
print("Constructed API URL:", api_url)

try:
    with open(file_path, "rb") as f:
        file_content = f.read()
except Exception as e:
    print(f"Error reading the file '{{file_path}}': {{e}}")
    exit(1)

encoded_content = base64.b64encode(file_content).decode("utf-8")

data = {{
    "branch": ref,
    "content": encoded_content,
    "commit_message": f"Add or update file {{file_path}}",
    "encoding": "base64"
}}

headers = {{
    "VAL": VAL
}}

response = requests.post(api_url, headers=headers, json=data)
if response.status_code == 400 and "already exists" in response.text:
    print("File already exists. Attempting to update (overwrite) it using PUT.")
    response = requests.put(api_url, headers=headers, json=data)

if response.status_code in (200, 201):
    print("File saved successfully.")
else:
    print(f"Error saving file: {{response.status_code}} - {{response.text}}")
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
        "model_id": modelid
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

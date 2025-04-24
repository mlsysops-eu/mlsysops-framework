import os
import docker
import yaml

template = """#!/usr/bin/python3
# Author John Byabazaire

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import pandas as pd
import joblib
import os
import json
from pydantic import create_model
import requests
from io import BytesIO
import base64
import urllib.parse

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
    
    try:
        loaded_model = joblib.load("{model}")
        print("Model loaded successfully!")
        if data_source == 0:
            data_dict = request.data.dict()
            df = pd.DataFrame([data_dict])
            result_pred = loaded_model.predict(df)
            if request.explanation:
                explanation_res = get_single_explanation(model_id,data_dict)
                if explanation_res:
                    return {{"inference": str(result_pred), "explanation":explanation_res}}
                else:
                    return {{"inference": str(result_pred), "explanation":"explanation_error"}}
            else:
                return {{"inference": str(result_pred)}}
        else:
            return {{"url": request.data_link}}
    except Exception as e:
        return {{"error": f"Failed to load model: {{str(e)}}"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port={port})
"""

def generate_dockerfile():
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


def build_and_push_image(model, registry_url, image_name, registry_username, registry_password, inference_data, datasource, model_id):
    params = {
        #"model_filename": model_name,
        "port": 8000,
        "schema_code":inference_data,
        "data_source":datasource,
        "model_id":model_id,
        "model":model
    }
    generated_code = template.format(**params)

    with open("/code/utils/api/main.py", "w") as f:
        f.write(generated_code)

    print("Python file 'main.py' has been created with the provided parameters.")

    generate_dockerfile()
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

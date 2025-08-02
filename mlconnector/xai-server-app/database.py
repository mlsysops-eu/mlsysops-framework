import requests
import io
from urllib.parse import urlparse
import pandas as pd
import joblib
from io import BytesIO
import base64
import urllib.parse
from manage_s3 import S3Manager
from dotenv import load_dotenv
import os
from agents.mlsysops.logger_util import logger

load_dotenv(verbose=True, override=True,dotenv_path='/.env')
manager = S3Manager(
            os.getenv("AWS_S3_BUCKET_DATA"),
            os.getenv("AWS_ACCESS_KEY_ID"),
            os.getenv("AWS_SECRET_ACCESS_KEY"),
            os.getenv("AWS_ACCESS_URL")
        )
#BASE_LINK= "http://daistwo.ucd.ie"
BASE_LINK= "http://api"
headers = {"PRIVATE-TOKEN": os.getenv("GIT_TOKEN")}
parsed_url = None
gitlab_host = None
path_parts = None
repo_path = None
branch = None
file_path = None

def proccessURL(url:str):
    global parsed_url, gitlab_host, path_parts, repo_path, branch, file_path
    parsed_url = urlparse(url)
    logger.info(parsed_url)
    gitlab_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
    path_parts = parsed_url.path.strip("/").split("/")
    repo_path = "/".join(path_parts[:2])
    branch = path_parts[4]
    file_path = "/".join(path_parts[5:])

def getProjectID():
    global parsed_url, gitlab_host, path_parts, repo_path, branch, file_path
    projects_url = f"{gitlab_host}/api/v4/projects"
    response = requests.get(projects_url, headers=headers)

    if response.status_code == 200:
        projects = response.json()
        project_id = next((p["id"] for p in projects if p["path_with_namespace"] == repo_path), None)
        if not project_id:
            logger.info(f"Project '{repo_path}' not found. Check the repository name.")
            exit()
    else:
        logger.critical(f"Failed to fetch projects: {response.status_code} - {response.text}")
        exit()
    return project_id

"""def downloadFile(url:str, isCSV=False):
    global parsed_url, gitlab_host, path_parts, repo_path, branch, file_path
    proccessURL(url)
    project_id = getProjectID()
    file_url = f"{gitlab_host}/api/v4/projects/{project_id}/repository/files/{file_path}/raw?ref={branch}"
    response = requests.get(file_url, headers=headers)
    if response.status_code == 200:
        file_buffer = io.BytesIO(response.content)
        file_buffer.seek(0)
        if isCSV:
            df = pd.read_csv(file_buffer)
            return df
        else:
            return file_buffer
    return None"""

def downloadFile(filename:str, isCSV=False):
    project_path = "side-api/ml_models"
    ref = "main" 
    encoded_project = urllib.parse.quote_plus(project_path)
    encoded_file = urllib.parse.quote_plus(filename)

    api_url = f"https://mlsysops-gitlab.e-ce.uth.gr/api/v4/projects/{encoded_project}/repository/files/{encoded_file}/raw?ref={ref}"
        
    headers = {
        "PRIVATE-TOKEN": os.getenv("GIT_TOKEN")
    }
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        file_buffer = io.BytesIO(response.content)
        file_buffer.seek(0)
        if isCSV:
            df = pd.read_csv(file_buffer)
            return df
        else:
            return file_buffer
    return None


def getModelDataById(modelId:str):
    """Get Request based on the """
    modelData = requests.get(BASE_LINK+"/model/get/"+modelId)
    csv_data = None
    model_file = None
    featurs_names = []
    if modelData.status_code == 200:
        responseData = modelData.json()  # Parse JSON response        
        for f in responseData["featurelist"]:
            featurs_names.append(f["feature_name"])
        csv_data = pd.DataFrame(downloadFile(responseData["training_data"][0]["training_data"], True))
        model_file = downloadFile(responseData["trained_model"][0]["modelname"])
        return model_file, csv_data, featurs_names
    else:
        logger.error(f"Error: {modelData.status_code}")
        return None, None, None

def getModelByManager(modelId:str):
    model_csv_name = modelId + ".csv"
    model_pkl_name = modelId + ".pkl"
    output_csv_path = f"./tmpData/{model_csv_name}"
    output_pkl_file = f"./tmpData/{model_pkl_name}"
    manager.download_file(model_csv_name,output_csv_path)
    manager.download_file(model_pkl_name,output_pkl_file)
    return output_pkl_file, pd.read_csv(output_csv_path)

#logger(getModelDataById("d11356fc-48c0-43d1-bc27-2723395f1dfe"))
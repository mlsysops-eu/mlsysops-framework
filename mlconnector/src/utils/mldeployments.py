# !/usr/bin/python3
# Author John Byabazaire


from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from fastapi import HTTPException
from models.mldeployment import MLDeployment
from schema.mldeployment import MLDeploymentCreate, MLDeploymentReturn
import json
from db.redis_setup import create_redis_connection
from utils.api.generate_dockerfile import build_and_push_image, generate_json
from dotenv import load_dotenv
from utils.mlmodels import get_model_by_id, get_model_files
from pydantic import create_model
import os
import uuid
import requests
import json
import ast
from textwrap import dedent
from utils.manage_s3 import S3Manager
from sqlalchemy import update
#myuuid = uuid.uuid4()

load_dotenv(verbose=True, override=True)


s3_manager = S3Manager(
    os.getenv("AWS_S3_BUCKET_DATA"),
    os.getenv("AWS_ACCESS_KEY_ID"),
    os.getenv("AWS_SECRET_ACCESS_KEY"),
    os.getenv("AWS_ACCESS_URL")
)

def extract_feature_names(feature_list):
    type_mapping = {
        'cont': "float",
        'cat': "str"
    }
    
    return {
        feature['feature_name']: type_mapping.get(feature['type'], None)
        for feature in feature_list
        if feature.get('kind') == 0
    }
async def deploy_ml_application(endpoint, payload):
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{endpoint}/ml/deploy_ml"
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error deploying ML application: {e}")
        return

    # On success
    print(f"Status Code: {response.status_code}")
    try:
        print("Response JSON:", response.json())
    except ValueError:
        print("Response Text:", response.text)

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


def generate_schema_code(flag=0, feature_list_str=None):
    if flag == 0:
        schema_code = dedent(f"""
            # Parse the feature list JSON string to a dict.
            feature_dict = json.loads('{feature_list_str}')
            # Map the type strings to actual Python types.
            type_mapping = {{
                "int": float,
                "str": str,
                "float": float
            }}
            # Create a field definition for each feature.
            # The ellipsis (...) marks the field as required.
            fields = {{
                key: (type_mapping.get(val, str), ...)
                for key, val in feature_dict.items()
            }}
            DataModel = create_model("DataModel", **fields)
            DynamicSchema = create_model("DynamicSchema", data=(DataModel, ...), explanation=(bool, ...))
        """)
    elif flag == 1:
        schema_code = dedent("""
            DynamicSchema = create_model("DynamicSchema", data_link=(str, ...), explanation=(bool, ...))
        """)
    
    return schema_code

async def get_deployment_by_id(db: AsyncSession, deployment_id: str):
    query = select(MLDeployment).where(MLDeployment.deployment_id == deployment_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_deployment_status(db: AsyncSession, deployment_id: str):
    BASE_URL = os.getenv('NOTHBOUND_API_ENDPOINT')
    url = f"{BASE_URL}/ml/status/{deployment_id}"
    #print(url)
    headers = {"Accept": "application/json"}
    
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Status fetch failed: {e}")
        return False

    try:
        data_dict = ast.literal_eval(resp.json()["status"])
        #update MLDeployment model status
        query = (
            update(MLDeployment)
            .where(MLDeployment.deployment_id == deployment_id)
            .values(status=data_dict["status"])
        )
        await db.execute(query)
        await db.commit()
        return resp.json()
    except ValueError:
        return resp.text
    

async def return_all_deployments(db: AsyncSession):
    BASE_URL = os.getenv('NOTHBOUND_API_ENDPOINT')
    url = f"{BASE_URL}/ml/list_all/"
    #print(url)
    headers = {"Accept": "application/json"}
    
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Status fetch failed: {e}")
        return False

    try:
        return resp.json()
    except ValueError:
        return resp.text

#return_all_deployments

async def update_deployment(
        db: AsyncSession,
        deployment_id:str,
        deployment: MLDeploymentCreate
    ):
    existing_deployment = await get_deployment_by_id(db=db, deployment_id=deployment_id)
    for field, value in deployment.model_dump(exclude_unset=True).items():
        setattr(existing_deployment, field, value)
    #async with db.begin():
    # db.add(db_car_owner)
    await db.commit()
    await db.refresh(existing_deployment)
    return existing_deployment

async def create_deployment(db: AsyncSession, deployment: MLDeploymentCreate, create_new=False):
    model = await get_model_by_id(db, model_id=deployment.modelid)
    file_model = await get_model_files(db, modelid=deployment.modelid, filekind="model")
    #file_require = await get_model_files(db, modelid=deployment.modelid, filekind="data")
    if(deployment.deployment_id ==""):
        deployment_id = str(uuid.uuid4())
    else:
        deployment_id = deployment.deployment_id
    #print(model.featurelist)
    #print(file_model)
    schema_code = ""
    if(deployment.inference_data==0):
        schema_code = generate_schema_code(flag=0, feature_list_str=json.dumps((extract_feature_names(model.featurelist))))
    else:  
        schema_code = generate_schema_code(flag=1)
    

    if model is None:
        raise HTTPException(status_code=404, detail="No model details found with that model_id")
    else:
        image_name = "registry.mlsysops.eu/usecases/augmenta-demo-testbed/"+deployment.modelid+":0.0.1"
        
        # download model file...
        local_model_path = prepare_model_artifact(s3_manager,  file_model[0].filename)
        build_and_push_image(
            #model.trained_model[0]['modelname'], 
            file_model[0].filename, 
            "registry.mlsysops.eu",
            image_name, 
            os.getenv("DOCKER_USERNAME"), 
            os.getenv("DOCKER_PASSWORD"),
            inference_data=schema_code,
            datasource=deployment.inference_data,
            model_id=deployment.modelid,
            model_owner=deployment.ownerid,
            deploymentid=deployment_id
        )
        placement_as_dict = {
            "clusterID": deployment.placement.clusterID,
            "node": deployment.placement.node,
            "continuum": deployment.placement.continuum
        }
        new_deployment = generate_json(
            deployment_id=deployment_id,
            image=image_name,
            placement=placement_as_dict,
            port=8000
        )
       
        #deployment_json = json.dumps(new_deployment)
        #print(str(new_deployment))
        
        #con = await create_redis_connection()
        #await con.rpush(os.getenv("DEPLOYMENT_QUEUE"), [str(deployment_json)])
        await deploy_ml_application(os.getenv("NOTHBOUND_API_ENDPOINT"), new_deployment)
    #return deployment
        res = MLDeploymentReturn (
            modelid = deployment.modelid,
            inference_data = deployment.inference_data,
            ownerid = deployment.ownerid,
            placement = deployment.placement,
            deployment_id = deployment_id,
            status = "waiting"
        )
        new_deployment = MLDeployment(
            modelid = deployment.modelid,
            ownerid = deployment.ownerid,
            placement = placement_as_dict,
            deployment_id = deployment_id,
            status = "waiting"
        )
        if create_new:
            existing_deployment = await get_deployment_by_id(db=db, deployment_id=deployment_id)
            if existing_deployment:
                # Update the existing deployment
                for key, value in deployment.model_dump(exclude_unset=True).items():
                    setattr(existing_deployment, key, value)
                db.add(existing_deployment)
                await db.commit()
                await db.refresh(existing_deployment)
        else:
            # Add new deployment
            db.add(new_deployment)
            await db.commit()
            await db.refresh(new_deployment)
        return res

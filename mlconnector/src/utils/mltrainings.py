# !/usr/bin/python3
# Author John Byabazaire


from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import inspect
from fastapi import HTTPException
from utils import mlmodels

from models.mltraining import MLTraining
from schema.mltraining import MLTrainCreate
from utils.generate_train import build_and_push_image, generate_json
import uuid
import os
import json
from utils.manage_s3 import S3Manager
from dotenv import load_dotenv
from agents.mlsysops.logger_util import logger

load_dotenv(verbose=True, override=True)


s3_manager = S3Manager(
    os.getenv("AWS_S3_BUCKET_DATA"),
    os.getenv("AWS_ACCESS_KEY_ID"),
    os.getenv("AWS_SECRET_ACCESS_KEY"),
    os.getenv("AWS_ACCESS_URL")
)

def prepare_file_artifact(s3_manager: S3Manager, file_name: str, download_dir: str = "/code/utils/train"):
    """
    Download the file from S3 into download_dir.
    Returns the local path to the downloaded file.
    """
    local_path = os.path.join(download_dir, file_name)
    # ensure the directory exists
    os.makedirs(download_dir, exist_ok=True)

    # download from S3
    s3_manager.download_file(object_name=file_name, download_path=local_path)
    logger.info(f"File downloaded to {local_path}")
    return local_path

async def get_train_deplyment_id(db: AsyncSession, modelid: str):
    #query = select(MLTraining).where(MLTraining.modelid == modelid)
    query = select(MLTraining).where(
        MLTraining.modelid == modelid,
        MLTraining.status != "completed"
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_training(db: AsyncSession, mltrain: MLTrainCreate):
    # model = await mlmodels.get_model_by_id(db, model_id=mltrain.modelid)
    model = await mlmodels.get_model_by_id(db, model_id=mltrain.modelid)
    file_code = await mlmodels.get_model_files(db, modelid=mltrain.modelid, filekind="code")
    file_data = await mlmodels.get_model_files(db, modelid=mltrain.modelid, filekind="data")
    deployment_id = str(uuid.uuid4())
    if model is None:
        raise HTTPException(status_code=404, detail="No model details found with that model_id")
    else:
        local_code_path = prepare_file_artifact(s3_manager, file_code[0].filename)
        local_data_path = prepare_file_artifact(s3_manager, file_data[0].filename)
        #logger(model[0][1].filename)
        image_name = "registry.mlsysops.eu/usecases/augmenta-demo-testbed/"+deployment_id+":0.0.1"
        build_and_push_image(
            mltrain.modelid, 
            "registry.mlsysops.eu",
            image_name, 
            os.getenv("DOCKER_USERNAME"), 
            os.getenv("DOCKER_PASSWORD"),
            file_data[0].filename,
            file_code[0].filename
        )
        placement_as_dict = {
            "clusterID": mltrain.placement.clusterID,
            "node": mltrain.placement.node,
            "continuum": mltrain.placement.continuum
        }
        new_deployment = generate_json(
            deployment_id=deployment_id,
            image=image_name,
            placement=placement_as_dict,
            port=8000
        )
        deployment_json = json.dumps(new_deployment)
        
        logger.debug(str(deployment_json))
        
        
        new_train = MLTraining(
            deployment_id = deployment_id,
            modelid = mltrain.modelid,
            status = "waiting",
            placement = placement_as_dict
        )
        #async with db.begin():
        db.add(new_train)
        await db.commit()
        await db.refresh(new_train)
        return new_train

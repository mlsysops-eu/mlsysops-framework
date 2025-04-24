# !/usr/bin/python3
# Author John Byabazaire


from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from utils import mlmodels

from models.mltraining import MLTraining
from schema.mltraining import MLTrainCreate
from utils.generate_train import generate_yaml, build_and_push_image
import uuid
import os
import json

async def get_train_deplyment_id(db: AsyncSession, modelid: str):
    #query = select(MLTraining).where(MLTraining.modelid == modelid)
    query = select(MLTraining).where(
        MLTraining.modelid == modelid,
        MLTraining.status != "completed"
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_training(db: AsyncSession, mltrain: MLTrainCreate):
    model = await mlmodels.get_model_by_id(db, model_id=mltrain.modelid)
    deployment_id = str(uuid.uuid4())
    if model is None:
        raise HTTPException(status_code=404, detail="No model details found with that model_id")
    else:
        image_name = "registry.mlsysops.eu/usecases/augmenta-demo-testbed/"+deployment_id+":0.0.1"
        build_and_push_image(
            mltrain.modelid, 
            "registry.mlsysops.eu",
            image_name, 
            os.getenv("DOCKER_USERNAME"), 
            os.getenv("DOCKER_PASSWORD"),
            model.training_data[0]['training_data'],
            model.training_data[0]["training_code"]
        )
        new_deployment = generate_yaml(
            deployment_id=deployment_id,
            image=image_name,
            clusterID=mltrain.placement.clusterID,
            node=mltrain.placement.node,
            continuum=mltrain.placement.continuum
        )
       
        deployment_json = json.dumps(new_deployment)
        print(str(deployment_json))
        
        placement_as_dict = {
            "clusterID": mltrain.placement.clusterID,
            "node": mltrain.placement.node,
            "continuum": mltrain.placement.continuum
        }
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

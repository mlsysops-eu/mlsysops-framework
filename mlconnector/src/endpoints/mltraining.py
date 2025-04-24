# !/usr/bin/python3
# Author John Byabazaire


import fastapi
from schema.mltraining import MLTrain, MLTrainCreate
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from db.db_setup import get_db
import utils.mltrainings as utl
from typing import List


router = fastapi.APIRouter()


@router.post("/mltraining/add", response_model=MLTrain, status_code=201, tags=["Training"])
async def add_new_training(
        request: Request,
        train: MLTrainCreate, 
        db: Session = Depends(get_db)
    ):
    mlmodel_train = await utl.get_train_deplyment_id(db=db, modelid=train.modelid)
    if mlmodel_train:
        raise HTTPException(status_code=400, detail="ML model training instance is already running")
    return await utl.create_training(db=db, mltrain=train)

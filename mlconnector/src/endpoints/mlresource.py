# !/usr/bin/python3
# Author John Byabazaire


import fastapi
from schema.mlresource import MLResource, MLResourceCreate
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from db.db_setup import get_db
import utils.mlresources as utl
from typing import List


router = fastapi.APIRouter()




@router.get("/mlresource/all",  response_model=List[MLResource], tags=["Feature"])
async def get_all_resource(
        request: Request,
        skip: int = 0, 
        limit: int = 100, 
        db: Session = Depends(get_db)
    ):
    model_features = await utl.return_all_model_features(db, skip=skip, limit=limit)
    if len(model_features) == 0:
        raise HTTPException(status_code=404, detail="No models features were not found")
    return model_features


@router.get("/mlresource/feature/{resource_id}",  response_model=MLResource, tags=["Feature"])
async def get_all_features_by_id(
        request: Request,
        resource_id: str,
        db: Session = Depends(get_db)
    ):
    
    model_feature = await utl.get_feature_by_id(db, resource_id=resource_id)
    if model_feature is None:
            raise HTTPException(status_code=404, detail="No model feature details found with that model_id")
    return model_feature


@router.get("/mlresource/mlmodel/{model_id}",  response_model=List[MLResource], tags=["Feature"])
async def get_all_features_by_model_id(
        request: Request,
        model_id: str,
        db: Session = Depends(get_db)
    ):
    ml_fetaure = await utl.get_feature_by_model_id(db, model_id=model_id)
    if len(ml_fetaure) == 0:
            raise HTTPException(status_code=404, detail="No model feature details found with that model_id")
    return ml_fetaure


@router.post("/mlresource/add", response_model=MLResource, status_code=201, tags=["Feature"])
async def add_new_resource(
        request: Request,
        feature: MLResourceCreate, 
        db: Session = Depends(get_db)
    ):
    mlmodel_fetaure = await utl.get_feature_by_id(db=db, resource_id=feature.resource_id)
    if mlmodel_fetaure:
        raise HTTPException(status_code=400, detail="ML model feature already registered")
    return await utl.create_fetaure(db=db, mlresource=feature)


@router.patch("/mlresource/{resource_id}", tags=["Feature"])
async def update_resource(resource_id: int):
    return {"transaction": []}


@router.delete("/mlresource/{resource_id}", tags=["Feature"])
async def delete_resourcc(transaction_id: int):
    return {"transaction": []}
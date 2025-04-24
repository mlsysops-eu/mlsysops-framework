# !/usr/bin/python3
# Author John Byabazaire

import fastapi
from schema.mlmodels import MLModel, MLModelCreate, MLModelDeploy, MLModelDeployRes, ModelTags, FileSchema
from fastapi import Depends, HTTPException, status, Request, Query,  File, UploadFile, Form
from sqlalchemy.orm import Session
from db.db_setup import get_db
import utils.mlmodels as utl
from typing import List, Optional
import os
from enum import Enum


router = fastapi.APIRouter()

class FileKind(str, Enum):
    model = "model"
    data = "data"
    code = "code"
    env = "env"

@router.post("/model/add",response_model=MLModel, status_code=201, tags=["Model"])
async def add_new_model(
        request: Request,
        model: MLModelCreate, 
        db: Session = Depends(get_db)
    ):
    return await utl.create_model(db=db, mlmodel=model)

@router.post("/model/{model_id}/upload", response_model=FileSchema, status_code=201, tags=["Model"])
async def upload_file_for_model(
    model_id: str,
    file: UploadFile = File(...),
    file_kind: FileKind = Form(...),
    db: Session = Depends(get_db)
):
    model_db = await utl.get_model_by_id(db, model_id)
    if model_db:
        # Create a FileSchema instance to represent the uploaded file metadata
        file_data = FileSchema(modelid=model_id, filekind=file_kind.value, filename=file.filename, contenttype=file.content_type)
        file_upload = await utl.upload_models(db, file, file_data)
        if file_upload:
            return file_data
        else:
            raise HTTPException(status_code=500, detail="Failed to upload file to S3")    
    else:
        raise HTTPException(status_code=404, detail="No model details found")


@router.get("/model/all",  response_model=List[MLModel], tags=["Model"])
async def get_all_models(
        request: Request,
        skip: int = 0, 
        limit: int = 100, 
        db: Session = Depends(get_db)
    ):
    models = await utl.return_all_models(db, skip=skip, limit=limit)
    if len(models) == 0:
        raise HTTPException(status_code=404, detail="No models were not found")
    return models

@router.get("/model/getkind/{modelkind}",  response_model=List[MLModel], tags=["Model"])
async def get_models_by_kind(
        request: Request,
        modelkind: str,
        db: Session = Depends(get_db)
    ):
    
    models = await utl.get_model_by_kind(db, modelkind=modelkind)
    if len(models) == 0:
            raise HTTPException(status_code=404, detail="No model details found")
    return models

@router.get("/model/search", response_model=List[MLModel], tags=["Model"])
async def get_models_by_tags(
    request: Request,
    model_tags: ModelTags = Depends(),
    db: Session = Depends(get_db)
):
    models = await utl.get_models_by_tags(db, tags=model_tags.tags)
    if not models:
        raise HTTPException(status_code=404, detail="No models found with the provided tags")
    return models



@router.get("/model/search", response_model=List[MLModel], tags=["Model"])
async def get_models_by_tags(
    request: Request,
    model_tags: ModelTags = Depends(),
    db: Session = Depends(get_db)
):
    models = await utl.get_models_by_tags(db, tags=model_tags.tags)
    if not models:
        raise HTTPException(status_code=404, detail="No models found with the provided tags")
    return models


@router.patch("/model/{model_id}", tags=["Model"])
async def update_model(model_id: str):
    return {"model": []}


@router.delete("/model/{model_id}", tags=["Model"])
async def delete_model(
        model_id: str,
        db: Session = Depends(get_db)
     ):
    existing_model = await utl.get_model_by_id(db=db, model_id=model_id)
    
    if existing_model is None:
        raise HTTPException(status_code=404, detail="Model was not found")
    await db.delete(existing_model)
    await db.commit()
    
    # Return a message indicating successful deletion
    return {"message": "Model was deleted successfully"}
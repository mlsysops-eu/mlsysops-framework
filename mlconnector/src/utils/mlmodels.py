# !/usr/bin/python3
# Author John Byabazaire


from sqlalchemy.orm import Session, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from fastapi import UploadFile

from models.mlmodels import MLModels, MLModelFiles
from schema.mlmodels import MLModelCreate, MLModelDeploy, MLModelDeployRes, FileSchema
import uuid
import os
from utils.manage_s3 import S3Manager
#myuuid = uuid.uuid4()


s3_manager = S3Manager(
    os.getenv("AWS_S3_BUCKET_DATA"),
    os.getenv("AWS_ACCESS_KEY_ID"),
    os.getenv("AWS_SECRET_ACCESS_KEY"),
    os.getenv("AWS_ACCESS_URL")
)

async def get_model_by_id(db: AsyncSession, model_id: str):
    query = select(MLModels).where(MLModels.modelid == model_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_model_join_by_id(db: AsyncSession, model_id: str):
    query = (
        select(MLModels, MLModelFiles)
        .join(MLModelFiles, MLModels.modelid == MLModelFiles.modelid)
        .where(MLModels.modelid == model_id)
    )
    result = await db.execute(query)
    # result.all() is a list of tuples: (MLModels, MLModelFiles)
    return result.all()

async def get_file_details(db: AsyncSession, file_id: str):
    query = select(MLModelFiles).where(MLModelFiles.fiileid == file_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

  
async def get_model_by_kind(db: AsyncSession, modelkind: str):
    query = select(MLModels).where(MLModels.modelkind == modelkind)
    result = await db.execute(query)
    return result.scalars().all()

async def get_model_file_by_id_type(db: AsyncSession, modelid: str, filetype: str):
    query = select(MLModelFiles).where(
        MLModelFiles.modelid == modelid,
        MLModelFiles.filekind == filetype
    )
    result = await db.execute(query)
    return result.scalars().all()

async def upload_models(db: AsyncSession, file: UploadFile, file_data: FileSchema):
    # Extract the extension from the original file name, if any
    _, ext = os.path.splitext(file_data.filename)
    new_filename = file_data.modelid + ext if ext else file_data.modelid

    temp_file_path = os.path.join("/tmp", new_filename)
    
    try:
        with open(temp_file_path, "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)
            file_data.filename = new_filename
            # check if the its model update..
            old_model = await get_model_file_by_id_type(db, file_data.modelid, file_data.filekind)
            #print(old_model)
            if len(old_model)==0:
                await save_model_file(db, file_data)
            else:
                update_data = FileSchema(
                        modelid=old_model[0].modelid,
                        filekind=old_model[0].filekind,
                        filename=old_model[0].filename,
                        contenttype=old_model[0].contenttype
                    )
                if file_data.file_kind =="model":
                    # after update trigger regeneration of application.
                    await update_model_file(db, old_model[0].fileid, update_data)
                    print("trigger")
                else:
                    await update_model_file(db, old_model[0].fileid, update_data)
    
        if not s3_manager.upload_file(temp_file_path):
            return False
    except Exception as e:
        #print(e)
        return False
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
    return True


async def get_models_by_tags(db: AsyncSession, tags: Optional[List[str]]):
    query = select(MLModels)
    if tags:
        # Apply the filter using the overlap operator
        query = query.filter(MLModels.modeltags.overlap(tags))
    result = await db.execute(query)
    return result.scalars().all()


async def return_all_models(db: AsyncSession, skip: int = 0, limit: int = 100):
    query = select(MLModels).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def create_deployment(db: AsyncSession, mlmodel: MLModelDeploy):
  return MLModelDeployRes (
      modelid = mlmodel.modelid,
      deploymentid = str(uuid.uuid4())
  )


async def create_model(db: AsyncSession, mlmodel: MLModels):
    hyperparameter_as_dict = [hyperparameter.dict() for hyperparameter in mlmodel.hyperparameter] if mlmodel.hyperparameter else None
    modelperformance_as_dict = [modelperformance.dict() for modelperformance in mlmodel.modelperformance] if mlmodel.modelperformance else None
    trainingresource_as_dict = [trainingresource.dict() for trainingresource in mlmodel.trainingresource] if mlmodel.hyperparameter else None
    runresource_as_dict = [runresource.dict() for runresource in mlmodel.runresource] if mlmodel.runresource else None
    featurelist_as_dict = [featurelist.dict() for featurelist in mlmodel.featurelist] if mlmodel.featurelist else None
    inference_as_dict = [inference.dict() for inference in mlmodel.inference] if mlmodel.inference else None
    #trained_model_as_dict = [trained_model.dict() for trained_model in mlmodel.trained_model] if mlmodel.trained_model else None
    #training_data_as_dict = [training_data.dict() for training_data in mlmodel.training_data] if mlmodel.training_data else None
    new_model = MLModels(
        modelid = str(uuid.uuid4()),
        modelname = mlmodel.modelname,
        modelkind = mlmodel.modelkind,
        #source_code = str(mlmodel.source_code),
        #trained_model = trained_model_as_dict,
        #training_data = training_data_as_dict,
        hyperparameter = hyperparameter_as_dict,
        modelperformance = modelperformance_as_dict,
        trainingresource = trainingresource_as_dict,
        runresource = runresource_as_dict,
        featurelist = featurelist_as_dict,
        inference = inference_as_dict,
        modeltags = mlmodel.modeltags
    )
    #async with db.begin():
    db.add(new_model)
    await db.commit()
    await db.refresh(new_model)
    return new_model


async def save_model_file(db: AsyncSession, file_data: FileSchema):
    new_file = MLModelFiles(
        fileid = str(uuid.uuid4()),
        modelid = file_data.modelid,
        filename = file_data.filename,
        filekind = file_data.filekind,
        contenttype = file_data.contenttype,
    )
    #async with db.begin():
    db.add(new_file)
    await db.commit()
    await db.refresh(new_file)
    return new_file


async def update_model(
        db: AsyncSession, 
        model_id: str,
        account: MLModelCreate 
    ):
    existing_model = await get_model_by_id(db=db, model_id=model_id)
    for field, value in account.model_dump(exclude_unset=True).items():
        setattr(existing_model, field, value)
    #async with db.begin():
    await db.commit()
    await db.refresh(existing_model)
    return existing_model

async def update_model_file(
        db: AsyncSession, 
        file_id: str,
        modelfile: FileSchema 
    ):
    existing_file_details = await get_file_details(db=db, file_id=file_id)
    for field, value in modelfile.model_dump(exclude_unset=True).items():
        setattr(existing_file_details, field, value)
    #async with db.begin():
    await db.commit()
    await db.refresh(existing_file_details)
    return existing_file_details
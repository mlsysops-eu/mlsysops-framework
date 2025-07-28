# !/usr/bin/python3
# Author John Byabazaire


from sqlalchemy.orm import Session, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import inspect
from sqlalchemy import text
from typing import List, Optional
from fastapi import UploadFile

from models.mlmodels import MLModels, MLModelFiles
from models.mldeployment import MLDeployment
from schema.mldeployment import MLDeploymentCreate
from schema.mlmodels import MLModelCreate, MLModelDeploy, MLModelDeployRes, FileSchema
import uuid
import os
import json
from utils.manage_s3 import S3Manager
import utils.mldeployments
#myuuid = uuid.uuid4()

from agents.mlsysops.logger_util import logger


s3_manager = S3Manager(
    os.getenv("AWS_S3_BUCKET_DATA"),
    os.getenv("AWS_ACCESS_KEY_ID"),
    os.getenv("AWS_SECRET_ACCESS_KEY"),
    os.getenv("AWS_ACCESS_URL")
)
def _serialize(obj):
    """
    Turn a SQLAlchemy ORM object into a plain dict by inspecting its columns.
    """
    return {
        col.key: getattr(obj, col.key)
        for col in inspect(obj).mapper.column_attrs
    }

async def update_deployments(db: AsyncSession, deployments: List[dict]):
    count = 1
    for row in deployments:
        logger.debug("Processing deployment: ", count, " of ", len(deployments))
        logger.debug("*"*20)
        # Convert the dictionary to a Pydantic model
        ml_deployment = MLDeploymentCreate(
            modelid=row['modelid'],
            ownerid=row['ownerid'],
            placement=row['placement'],
            deployment_id=row['deployment_id'],
            inference_data=0,  
        )
        results = await utils.mldeployments.create_deployment(db=db, deployment=ml_deployment, create_new=True)
        logger.info("Deployment created: ", results)
        count += 1
       
        """# Check if the deployment is already in the database
        existing_deployment = await db.execute(
            select(MLDeployment).where(MLDeployment.deploymentid == row.deploymentid)
        )
        existing_deployment = existing_deployment.scalar_one_or_none()

        if existing_deployment:
            # Update the existing deployment
            for key, value in row.__dict__.items():
                setattr(existing_deployment, key, value)
            db.add(existing_deployment)
        else:
            # Add new deployment
            db.add(row)"""

async def get_model_by_id(db: AsyncSession, model_id: str):
    query = select(MLModels).where(MLModels.modelid == model_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_model_join_by_id(db: AsyncSession, model_id: str):
    sql = text("""
        SELECT
          m.*,
          f.*
        FROM mlmodels AS m
        JOIN mlmodelfiles AS f
        ON m.modelid = f.modelid
        WHERE m.modelid = :model_id
    """)
    result = await db.execute(sql, {"model_id": model_id})
    return result.fetchall()

async def get_file_details(db: AsyncSession, file_id: str):
    query = select(MLModelFiles).where(MLModelFiles.fileid == file_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_model_files(db: AsyncSession, modelid: str, filekind:str):
    query = (
        select(MLModelFiles)
        .where(
            MLModelFiles.modelid == modelid,
            MLModelFiles.filekind == filekind
        )
    )
    result = await db.execute(query)
    return result.scalars().all()
  
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

async def upload_models(
    db: AsyncSession,
    file: UploadFile,
    file_data: FileSchema
) -> bool:
    """
    Save or update a model file record, upload to S3, then—
    only if S3 upload succeeded and it’s a `model` file—
    update any pending deployments for that model.
    """
    # 1) Prepare temp filename
    _, ext = os.path.splitext(file_data.filename)
    file_data.filename = f"{file_data.modelid}{ext or ''}"
    temp_path = os.path.join("/tmp", file_data.filename)

    try:
        # 2) Write upload to disk
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        # 3) Insert or update file record
        existing = (await get_model_file_by_id_type(db, file_data.modelid, file_data.filekind)) or []
        is_new = not existing
        if is_new:
            await save_model_file(db, file_data)
        else:
            old = existing[0]
            # preserve existing metadata but bump filename if needed
            update_data = FileSchema(
                modelid=old.modelid,
                filekind=old.filekind,
                filename=file_data.filename,
                contenttype=old.contenttype,
            )
            await update_model_file(db, old.fileid, update_data)

        # 4) Upload to S3
        uploaded = s3_manager.upload_file(temp_path)
        if not uploaded:
            return False

        # 5) Only for model‐kind updates, update deployments
        if not is_new and file_data.filekind == "model":
            stmt = (
                select(MLDeployment)
                .where(
                    MLDeployment.modelid == file_data.modelid,
                    MLDeployment.status  != "deployed"
                )
            )
            result = await db.execute(stmt)
            pending = result.scalars().all()

            # serialize and push to your update_deployments routine
            payload = [_serialize(dep) for dep in pending]
            await update_deployments(db, payload)

        return True

    except Exception as e:
        logger.error(f"upload_models failed: {e}")
        return False

    finally:
        # 6) Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


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
    drift_detection_as_dict = [drift_detection.dict() for drift_detection in mlmodel.drift_detection] if mlmodel.drift_detection else None
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
        modeltags = mlmodel.modeltags,
        drift_detection = drift_detection_as_dict
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
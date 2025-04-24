# !/usr/bin/python3
# Author John Byabazaire


from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from fastapi import HTTPException
from models.mldeployment import MLDeploymentOps
from schema.mloperations import MLDeploymentOposCreate, MLDeploymentOposReturn
import json
from dotenv import load_dotenv
from pydantic import create_model
import os
import uuid
#myuuid = uuid.uuid4()

load_dotenv(verbose=True, override=True)

async def get_deployment_ops_by_owner(db: AsyncSession, ownerid: str):
    query = select(MLDeploymentOps).where(MLDeploymentOps.ownerid == ownerid)
    result = await db.execute(query)
    return result.scalars().all()

async def get_deployment_ops_by_deployment(db: AsyncSession, deploymentid: str):
    query = select(MLDeploymentOps).where(MLDeploymentOps.deploymentid == deploymentid)
    result = await db.execute(query)
    return result.scalars().all()

async def save_opos(db: AsyncSession, mloperation: MLDeploymentOposCreate):
    new_opos = MLDeploymentOps(
        operationid = str(uuid.uuid4()),
        timestamp = mloperation.timestamp,
        ownerid = mloperation.ownerid,
        modelid = mloperation.modelid,
        data = mloperation.data,
        result = mloperation.result,
        deploymentid = mloperation.deploymentid,
    )
    #async with db.begin():
    db.add(new_opos)
    await db.commit()
    await db.refresh(new_opos)
    return new_opos
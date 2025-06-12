# !/usr/bin/python3
# Author John Byabazaire


import fastapi
from schema.mldeployment import MLDeploymentReturn, MLDeploymentCreate
from schema.mloperations import MLDeploymentOposReturn, MLDeploymentOposCreate
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from db.db_setup import get_db
import utils.mldeployments as utl
import utils.mloperations as utility
from typing import List


router = fastapi.APIRouter()

@router.get("/deployment/all",  tags=["Deployments"])
async def get_all_deployments(
        request: Request,
        skip: int = 0, 
        limit: int = 100, 
        db: Session = Depends(get_db)
    ):
    deployment = await utl.return_all_deployments(db)
    if len(deployment) == 0:
        raise HTTPException(status_code=404, detail="No deployments were not found")
    return deployment


@router.post("/deployment/add", response_model=MLDeploymentReturn, status_code=201, tags=["Deployments"])
async def add_new_deployment(
        request: Request,
        deploy: MLDeploymentCreate, 
        db: Session = Depends(get_db)
    ):
    #mldeployment = await utl.get_deployment_by_id(db=db, deployment_id=deploy.deployment_id)
    #if mldeployment:
    #    raise HTTPException(status_code=400, detail="ML model deployment already running")
    deploy_obj = await utl.create_deployment(db=db, deployment=deploy)
    return deploy_obj


@router.post("/deployment/add/operation", response_model=MLDeploymentOposReturn, status_code=201, tags=["Deployments"])
async def add_new_opos_deployment(
        request: Request,
        deploy_ops: MLDeploymentOposCreate, 
        db: Session = Depends(get_db)
    ):
    deploy_obj = await utility.save_opos(db=db, mloperation=deploy_ops)
    return deploy_obj


@router.get("/deployment/get/status/{deployment_id}", tags=["Deployments"])
async def get_deployment_status(
        request: Request,
        deployment_id: str,
        db: Session = Depends(get_db)
    ):
    deployment = await utl.get_deployment_status(db, deployment_id=deployment_id)
    if deployment is False:
            raise HTTPException(status_code=404, detail="No deployment with matching id was found")
            #return {"status": "Pending"}
    return {"response": str(deployment)}


@router.get("/deployment/get/opos/{ownerid}", response_model=List[MLDeploymentOposReturn], tags=["Deployments"])
async def get_deployment_ops_by_owner(
        request: Request,
        ownerid: str,
        db: Session = Depends(get_db)
    ):
    opos = await utility.get_deployment_ops_by_owner(db, ownerid=ownerid)
    if len(opos) == 0:
            raise HTTPException(status_code=404, detail="No deployment with matching id was found")
            #return {"status": "Pending"}
    return opos

"""
@router.patch("/deployment/{deployment_id}", tags=["Deployments"])
async def update_deployments(
        request: Request,
        deploy: MLDeploymentCreate, 
        deployment_id: str,
        db: Session = Depends(get_db),
    ):
    existing_deployment = await utl.get_deployment_by_id(db=db, deployment_id=deployment_id)
    
    if existing_deployment is None:
        raise HTTPException(status_code=404, detail="Deployment was not found")
    return await utl.update_deployment(db=db, deployment_id=deployment_id, deployment=deploy)
"""

@router.delete("/deployment/{deployment_id}", tags=["Deployments"])
async def delete_deployment(
        deployment_id: str,
        db: Session = Depends(get_db)
    ):
    existing_deployment = await utl.get_deployment_by_id(db=db, deployment_id=deployment_id)
    
    if existing_deployment is None:
        raise HTTPException(status_code=404, detail="Deployment was not found")
    await db.delete(existing_deployment)
    await db.commit()
    
    # Return a message indicating successful deletion
    return {"message": "Deployment was deleted successfully"}
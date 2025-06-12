# !/usr/bin/python3
# Author John Byabazaire


from pydantic import BaseModel, validator, HttpUrl, Field
from typing import List, Optional, Dict, Union, List


class Placement(BaseModel):
    clusterID: Optional[str] = Field(
        None, 
        example="UTH-Internal-testbed", 
        description="ID of the cluster, or "'*'" to deploy on any cluster"
    )
    node: Optional[str] = Field(
        None, 
        example="mls-drone", 
        description="Node ID, or '*' to deploy on any node"
    )
    continuum: Optional[str] = Field(
        None, 
        example="Edge", 
        description="continuum ID, or '*' to deploy on any where"
    )
    #bool = Field(False, description="Set to True to deploy at continuum level")


class MLDeploymentBase(BaseModel):
    """
    Used to create a ml model deployment
    """
    modelid:str = Field(..., description="ID of the model to deploy")
    ownerid:str = Field(..., description="ID of the agent deploying the model")
    placement:Placement = Field(..., description="Define where to place the model. If both clusterID and node are set to '*' model is deployed anywhere.")


class MLDeploymentCreate(MLDeploymentBase):
    deployment_id:Optional[str]
    inference_data:int = Field(..., description="How the inference data will be passed eg. 0 for values, 1 for link to data. The link MUST return .csv file")
    

class MLDeploymentReturn(MLDeploymentBase):
    """
    Used to return an ml model deployment
    """
    deployment_id:str
    status:str
    

    class Config:
        from_attributes = True

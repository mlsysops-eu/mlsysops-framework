# !/usr/bin/python3
# Author John Byabazaire


from enum import Enum
from pydantic import BaseModel, validator, HttpUrl, Field
from typing import List, Optional, Dict, Union, List



class Placement(BaseModel):
    clusterID: Optional[str] = Field(
        None, 
        example="UTH-Internal-testbed", 
        description="ID of the cluster, or '*' to deploy on any cluster"
    )
    node: Optional[str] = Field(
        None, 
        example="mls-drone", 
        description="Node ID, or '*' to deploy on any node"
    )
    continuum: bool = Field(False, description="Set to True to deploy at continuum level")


class MLTrainBase(BaseModel):
    """
    Used to create a Training instance
    """
    modelid:str
    placement:Placement = Field(..., description="Define where to place the model. If both clusterID and node are set to '*' model is deployed anywhere.")




class  MLTrainCreate( MLTrainBase):
    ...


class  MLTrain( MLTrainBase):
    deployment_id:str
    status:str
    

    class Config:
        from_attributes = True

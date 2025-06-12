# !/usr/bin/python3
# Author John Byabazaire


from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, validator, HttpUrl, Field
from fastapi import  Query

class Hyperparameter(BaseModel):
    parameter: str = Field(None, description="Hyperparameters, eg 'max_depth'")
    value: int = Field(None, description="Hyperparameter value, eg '5'")

class DriftDetection(BaseModel):
    is_true: int = Field(0, description="Set the value to 1 to turn on drift detection, otherwise 0")
    method: int = Field(0, description="Method used to detect drift, eg '0', Mean-Shift, '1', FourierMMD and  '2' for Kolmogorov-Smirnov test")


class FileSchema(BaseModel):
    modelid: str
    filekind: str
    filename: str
    contenttype: str

    model_config = {
        "from_attributes": True
    }

class TrainedModel(BaseModel):
    modelname: str = Field(
        None, 
        example="logistic_regression_model.pkl",
        description="Name of trained model"
    )
    githublink: str =  Field(
        None, 
        example="https://mlsysops-gitlab.e-ce.uth.gr/toycase/ml/-/raw/main/logistic_regression_model.pkl",
        description="Link to github with freezed traied model"
    )
 
class ModelTags:
    def __init__(
        self, 
        tags: Optional[List[str]] = Query(
            None, 
            description="List of model tags to filter models by (e.g., /model/search?tags=regression&tags=fast)"
        )
    ):
        self.tags = tags
    
class Inference(BaseModel):
    type: Optional[str] = Field(None, description="Defines how inference data is passed eg 'data' to pass list [16], or 'link' to pass reference to the data")
    value: Optional[str]

class TrainingData(BaseModel):
    training_data: Optional[str] = Field(None, description="Model training data (.csv filename)")
    training_code: Optional[str] = Field(None, description="Model training code (.py filename)")


class FeatureList(BaseModel):
    feature_name: Optional[str] = Field(None, description="The name of the feature, eg time_ms")
    type: Optional[str] = Field(None, description="The type of data, eg 'cont' for continous, or 'cat' for categorical")
    kind: Optional[int] = Field(None, description="If the feature is dependant, or independent 0, 1")
    units: Optional[int] = Field(None, description="Units")

class ModelPerformance(BaseModel):
    metric: Optional[str] = Field(None, description="The metric used to evaluate performance of the model, eg 'F1'")
    order: Optional[int] = Field(None, description="If more than one are defined order of precedence eg 1")
    threshold: Optional[int] = Field(None, description="Training threshold")

class TrainingResource(BaseModel):
    resource_name: Optional[str] = Field(None, description="The name of the resource, e.g., GPU or HDD")
    value: Optional[int]= Field(None, description="The numeric value of the resource, e.g., 32 or 30")
    deploy: Optional[str]= Field(None, description="Where the model will be trained, e.g., 'any', or '10.29.2.4'")

class RunResource(BaseModel):
    resource_name: Optional[str] = Field(None, description="The name of the resource, e.g., GPU or HDD")
    value: Optional[int]= Field(None, description="The numeric value of the resource, e.g., 32 or 30")
    deploy: Optional[str]= Field(None, description="Where the model will be run, e.g., 'any', or '10.29.2.4'")


class MLModelBase(BaseModel):
    """
    Used to create a ml model
    """
    #modelid:str
    modelname:str =  Field(..., description="Name of the ML model eg 'RandomForest'")
    modelkind:str =  Field(..., description="The type of model to be built. This can be classification, regression, or clustering")
    #source_code: HttpUrl =  Field(..., description="Link to github with source used to train the model")
    #trained_model: List[TrainedModel] =  Field(None, description="Details of trained model")
    #training_data:List[TrainingData] =  Field(..., description="Model training code (python file) and model training data (.csv file name.)")
    hyperparameter: Optional[List[Hyperparameter]] = Field(None, description="Hyperparameters and corresponding values")
    modelperformance: Optional[List[ModelPerformance]] = Field(None, description="List of metric used to evaluate the ML model")
    trainingresource: List[TrainingResource] = Field(None, description="List of training resources")
    runresource: Optional[List[RunResource]] = Field(None, description="List of running resources")
    featurelist: Optional[List[FeatureList]] = Field(None, description="List of model feature")
    inference:Optional[List[Inference]] = Field(None, description="How to pass the inference data")
    modeltags: Optional[List[str]] = Field(None, description="List of key tags to search model")
    #file_data:FileSchema = Field(..., description="model")
    drift_detection:Optional[List[DriftDetection]] = Field(..., description="Set the value to 1 to turn on drift detection, otherwise 0")

class MLModelDeploy(BaseModel):
    modelid:str

class MLModelDeployRes(MLModelDeploy):
    modelid:str
    deploymentid:str


class MLModelCreate(MLModelBase):
    ...


class MLModel(MLModelBase):
    """
    Used to return an ml model
    """
    modelid:str

    class Config:
        from_attributes = True


class MLModelJoin(MLModelBase):
    """
    Used to return an ml model
    """
    modelid:str
    filekind: str
    filename: str
    contenttype: str

    class Config:
        from_attributes = True
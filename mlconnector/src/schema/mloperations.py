#!/usr/bin/python3
# Author John Byabazaire

from pydantic import BaseModel, Field, validator
from datetime import datetime, timezone

class MLDeploymentOposBase(BaseModel):
    ownerid: str = Field(..., description="ID of the agent deploying the model")
    deploymentid: str = Field(..., description="ID of the agent deployment")
    modelid: str = Field(..., description="ID of the ML model being used")
    data: str = Field(..., description="JSON string of the inference data")
    result: str = Field(..., description="JSON string of the inference result from the model")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of the operation")

    @validator('timestamp', pre=True, always=True)
    def ensure_utc(cls, v):
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

class MLDeploymentOposCreate(MLDeploymentOposBase):
    ...

class MLDeploymentOposReturn(MLDeploymentOposBase):
    operationid: str = Field(..., description="Unique operation id")

    class Config:
        from_attributes = True

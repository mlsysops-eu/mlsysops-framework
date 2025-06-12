# !/usr/bin/python3
# Author John Byabazaire


from enum import Enum
from pydantic import BaseModel


    
class MLResourceBase(BaseModel):
    """
    Used to create a Resource type
    """
    resource_id:str
    explanation_flag:int
    modelrecall:int
    modelprecision:int
    modelaccuracy:int
    min_core:int
    min_ram:int
    min_disk:int
    input_type:str
    out_type:str
    modelid:str




class MLResourceCreate(MLResourceBase):
    ...


class MLResource(MLResourceBase):
    resource_id:str
    explanation_flag:int
    modelrecall:int
    modelprecision:int
    modelaccuracy:int
    min_core:int
    min_ram:int
    min_disk:int
    input_type:str
    out_type:str
    modelid:str
    

    class Config:
        from_attributes = True

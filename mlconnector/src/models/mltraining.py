# !/usr/bin/python3
# Author John Byabazaire


from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from db.db_setup import Base
#from models.mixins import Timestamp


class MLTraining(Base):
    __tablename__ = "mltraining"
    deployment_id = Column(String, primary_key=True)
    modelid = Column(String, nullable=False)
    status = Column(String, nullable=False)
    placement = Column(JSONB, nullable=True)
    
    


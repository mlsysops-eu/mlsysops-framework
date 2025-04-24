# !/usr/bin/python3
# Author John Byabazaire

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.db_setup import Base
#from models.mixins import Timestamp


class MLDeployment(Base):
    __tablename__ = "mldeployments"
    deployment_id = Column(String, primary_key=True)
    modelid = Column(String, nullable=False)
    status = Column(String, nullable=False)
    ownerid = Column(String, nullable=False)
    placement = Column(JSONB, nullable=True)
    
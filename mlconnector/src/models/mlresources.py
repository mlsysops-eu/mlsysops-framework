# !/usr/bin/python3
# Author John Byabazaire


from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Enum, Text, ARRAY
from sqlalchemy.orm import relationship

from db.db_setup import Base
#from models.mixins import Timestamp


class MLResources(Base):
    __tablename__ = "mlresources"
    resource_id = Column(String(32), primary_key=True)
    explanation_flag = Column(Integer, nullable=False)
    modelrecall = Column(Integer, nullable=False)
    modelprecision = Column(Integer, nullable=False)
    modelaccuracy = Column(Integer, nullable=False)
    min_core = Column(Integer, nullable=False)
    min_ram = Column(Integer, nullable=False)
    min_disk = Column(Integer, nullable=False)
    input_type = Column(String(20),  nullable=False)
    out_type = Column(String(20),  nullable=False)
    modelid = Column(String(32), ForeignKey('mlmodels.modelid'))
    


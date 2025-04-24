# !/usr/bin/python3
# Author John Byabazaire

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from db.db_setup import Base
#from models.mixins import Timestamp


class MLModels(Base):
    __tablename__ = "mlmodels"
    modelid = Column(Text, primary_key=True)
    modelname = Column(String(100), nullable=False)
    modelkind = Column(String(50), nullable=False)
    #source_code = Column(Text, nullable=False)
    #trained_model = Column(JSONB, nullable=True)
    #training_data = Column(JSONB, nullable=False)
    hyperparameter = Column(JSONB, nullable=True)
    modelperformance = Column(JSONB, nullable=True)
    trainingresource = Column(JSONB, nullable=True)
    runresource = Column(JSONB, nullable=True)
    featurelist = Column(JSONB, nullable=True)
    inference = Column(JSONB, nullable=True)
    modeltags = Column(ARRAY(String), nullable=True)
    #created_at = Column(DateTime, default=datetime.utcnow())
    #updated_at = Column(DateTime, onupdate=datetime.utcnow())

class MLModelFiles(Base):
    __tablename__ = "mlmodelfiles"
    fileid = Column(Text, primary_key=True)
    modelid = Column(Text, ForeignKey('mlmodels.modelid'))
    filename = Column(String(50), nullable=False)
    filekind = Column(Text, nullable=False)
    contenttype = Column(Text, nullable=False)
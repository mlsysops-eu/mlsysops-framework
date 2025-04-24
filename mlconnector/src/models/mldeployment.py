# !/usr/bin/python3
# Author John Byabazaire

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from datetime import datetime, timezone

from db.db_setup import Base


class MLDeployment(Base):
    __tablename__ = "mldeployments"

    deployment_id = Column(String, primary_key=True)
    modelid = Column(String, nullable=False)
    status = Column(String, nullable=False)
    ownerid = Column(String, nullable=False)
    placement = Column(JSONB, nullable=True)

    operations = relationship("MLDeploymentOps", back_populates="deployment")


class MLDeploymentOps(Base):
    __tablename__ = "mldeploymentsops"

    operationid = Column(String, primary_key=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ownerid = Column(String, nullable=False)
    modelid = Column(String, nullable=False)
    data = Column(String, nullable=False)
    result = Column(String, nullable=False)
    deploymentid = Column(String, ForeignKey("mldeployments.deployment_id"), nullable=False)

    deployment = relationship("MLDeployment", back_populates="operations")

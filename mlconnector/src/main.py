# !/usr/bin/python3
# Author John Byabazaire


import json
import os

from endpoints import mldeployment, mlmodels, mltraining
from fastapi import FastAPI

from db.db_setup import engine
from fastapi.middleware.cors import CORSMiddleware
#from fastsession import FastSessionMiddleware, MemoryStore
from starlette.middleware.sessions import SessionMiddleware

# Comment to autogenerate with alembic
with open(
        os.path.join(os.path.dirname(__file__), "endpoints/endpoint_tags.json")
    ) as f:
    tags_metadata = f.read()


app = FastAPI(
    title="MLSysOps ML Integration API",
    description="Machine Learning for Autonomic System Operation in the Heterogeneous Edge-Cloud Continuum",
    version="1.0.1",
    openapi_tags=json.loads(tags_metadata)
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    #allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    #expose_headers=["X-CSRF-Token"]
)
#app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET"))

app.include_router(mlmodels.router)
#app.include_router(mltraining.router)
app.include_router(mldeployment.router)

#app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET"))
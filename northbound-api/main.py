import uvicorn
from fastapi import FastAPI
from endpoints import applications, infrastructure, management


app = FastAPI(title="MLSysOps NorthBound API",
		description="Is API that the application owners and infrastructure administrators can use to interact with the MLSysOps platform.",
		version="1.0")

# Register each router with a prefix to organize routes
app.include_router(applications.router, prefix="/apps")
app.include_router(infrastructure.router, prefix="/infra")
app.include_router(management.router, prefix="/manage")

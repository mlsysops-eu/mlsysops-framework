import uvicorn
from fastapi import FastAPI


# generate MLSysOps CRD model
from generate_model import generate_pydantic_schemas

print("Generating MLSysOps CRD model...")
generated = generate_pydantic_schemas(schemas_dir="schemas")
print(f"Generated Pydantic models at: {generated}")




from endpoints import applications, management, ml_models
from redis_setup import redis_mgt as rm

app = FastAPI(title="MLSysOps NorthBound API",
              description="Is API that the application owners and infrastructure administrators can use to interact "
                          "with the MLSysOps platform.",
              version="1.0")

# 1) Create & connect your Redis client exactly once:
redis_client = rm.RedisManager()
redis_client.connect()

# 2) Attach it to `app.state` so that any route handler (or router) can fetch it later:
app.state.redis = redis_client

# Register each router with a prefix to organize routes
app.include_router(applications.router, prefix="/apps")
app.include_router(ml_models.router, prefix="/ml")
app.include_router(management.router, prefix="/manage")

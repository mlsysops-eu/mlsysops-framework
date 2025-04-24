#!/bin/bash

# Run database migration
alembic revision --autogenerate -m "Initial load"
alembic upgrade head

# start server
uvicorn main:app --host "0.0.0.0" --port "8090"
## MLConnector Setup Guide

This guide will walk you through setting up and running the MLConnector  using Docker.

---

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- **Docker**: Install Docker Engine and Docker Compose from [Docker’s official website](https://www.docker.com/).

---

## Environment Variables

The MLConnector relies on several external components. Define the following environment variables in your shell or an `.env` file:

### 1. Docker Registry
The MLConnector dynamically creates and stores docker images for inference applications used within MYLSysOps. As such, it needs to to be able to communicate to a registry weather public, or private. This application was tested with docker registry. For further information on docker registry [check](https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-a-registry/).

- `DOCKER_USERNAME`: Your Docker registry username
- `DOCKER_PASSWORD`: Your Docker registry password

### 2. AWS (File Storage)
The MLConnector uses an external storage service, S3 to store it's data including training data and other files. You will need to setup and S3 bucket, or S3 compatible service to complete this setup. After, please provide the following details. If you do not have access to S3 bucket, or S3 compatible service, please contact us and we can help setup a temporarily one. 
- `AWS_ACCESS_URL`: AWS S3 endpoint URL
- `AWS_ACCESS_KEY_ID`: AWS access key ID
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key
- `AWS_S3_BUCKET_DATA`: Name of the S3 bucket for data

### 3. PostgreSQL Database
This is used for internal communication of the varrious services. You can setup an external database service if you like. For simplicity you can you use the default values;
- `POSTGRES_DB`: PostgreSQL database name (default, `mlmodel`)
- `POSTGRES_USER`: PostgreSQL username (default, `postgres`)
- `POSTGRES_PASSWORD`: PostgreSQL password (default, `strongpassword`)
- `PGADMIN_DEFAULT_EMAIL`: pgAdmin default login email (default, `user@mail.com`)
- `PGADMIN_DEFAULT_PASSWORD`: pgAdmin default login password (default, `strongpassword`)
- `DB_HOST_NAME`: Database host (e.g., `database`, This corresponds to the name of the container)
- `DB_PORT`: Database port (default: `5432`)
- `DB_DRIVER`: Database driver string (default, `postgresql+asyncpg`)  **NOTE:** Only use an async driver

### 4. Northbound API Endpoint
The MLConnector  communicates with part of the MYLSyops via the `NORTHBOUND_API`. Please set this value to the right endpoint.
- `NORTHBOUND_API_ENDPOINT`: Base URL for the Northbound API (e.g., `http://your-host:8000`)

---

## Running the Application

1. **Start the Docker Containers**

   ```bash
   docker compose up -d
   ```

   This command builds and launches all required services in detached mode.

2. **View Container Logs**

   ```bash
   docker compose logs -f
   ```

---

## Accessing the API Documentation

Once the services are up and running, open your browser and navigate to:

```
http://<your-host>:8090/redoc
```

Replace `<your-host>` with your server’s hostname or `localhost` if running locally.

---

## Usage Example

### 1) Add ML Models

```bash
curl -X 'POST' \
  'http://localhost:8090/model/add' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "modelname": "GradientBoostingRegressor",
  "modelkind": "Regressor",
  "hyperparameter": [
    {
      "parameter": "string",
      "value": 0
    }
  ],
  "modelperformance": [
    {
      "metric": "string",
      "order": 0,
      "threshold": 0
    }
  ],
  "trainingresource": [
    {
      "resource_name": "string",
      "value": 0,
      "deploy": "string"
    }
  ],
  "runresource": [
    {
      "resource_name": "string",
      "value": 0,
      "deploy": "string"
    }
  ],
  "featurelist": [
    {
      "feature_name": "size",
      "type": "cont",
      "kind": 0,
      "units": 0
    },
    {
      "feature_name": "time_of_day",
      "type": "cat",
      "kind": 0,
      "units": 0
    },
    {
      "feature_name": "minute",
      "type": "cat",
      "kind": 0,
      "units": 0
    },
    {
      "feature_name": "second",
      "type": "cat",
      "kind": 0,
      "units": 0
    },
    {
      "feature_name": "hour",
      "type": "cat",
      "kind": 0,
      "units": 0
    },
    {
      "feature_name": "day_of_week",
      "type": "cat",
      "kind": 0,
      "units": 0
    },
    {
      "feature_name": "download_time_ms",
      "type": "cont",
      "kind": 1,
      "units": 0
    }
  ],
  "inference": [
    {
      "type": "string",
      "value": "string"
    }
  ],
  "modeltags": [
    "regression",
    "fast"
  ]
}'
```

### 2) Add Model Files

Upload model files (pickled model `.pkl`, training code `.py`, etc.) using the CC storage system:

```bash
curl -X 'POST' \
  'http://localhost:8090/model/b2078e0e-e2f3-4870-840c-7f9fbf2ab76d/upload' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@model_backend_id_144.pkl' \
  -F 'file_kind=model'
```

> **Note:** The UUID `b2078e0e-e2f3-4870-840c-7f9fbf2ab76d` in the endpoint path is your `model_id`.

---

## Troubleshooting

- **Port Conflicts**: Ensure ports `8090` (API docs) and your database port are available.
- **Environment Variables**: Verify all required variables are set. Use `docker compose config` to inspect the interpolated configuration.
- **Docker Connectivity**: Ensure Docker Engine is running and your user has permissions to run Docker commands.
- **API Error Codes**: All status codes and error messages can be accessed via: `http://<your-host>:8090/redoc`

---

## License

***

---


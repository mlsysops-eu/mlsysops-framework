# Variables
PLATFORMS := linux/arm64/v8,linux/amd64

DOCKER_BUILDX=docker buildx build

# Default tags (can be overridden from CLI)
NB_API_TAG ?=  registry.mlsysops.eu/agent/northbound-api
CI_COMMIT_TAG ?= 0.0.0

# Individual targets
nb_api:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} -t $(NB_API_TAG):$(CI_COMMIT_TAG) -f Dockerfile --push .

# Build all targets
all: nb_api
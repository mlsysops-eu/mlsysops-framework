# Variables
PLATFORMS := linux/amd64 #,linux/arm64/v8

DOCKER_BUILDX=docker buildx build

# Default tags (can be overridden from CLI)
NODE_AGENT_TAG ?=  registry.mlsysops.eu/agent/agents/node
CLUSTER_AGENT_TAG ?= registry.mlsysops.eu/agent/agents/cluster
CONTINUUM_AGENT_TAG ?= registry.mlsysops.eu/agent/agents/continuum

CI_COMMIT_TAG ?= 0.0.0

module:
	python3 -m build

node_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} -t $(NODE_AGENT_TAG):$(CI_COMMIT_TAG) -f node/Dockerfile --push node

cluster_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} -t $(CLUSTER_AGENT_TAG):$(CI_COMMIT_TAG) -f cluster/Dockerfile --push cluster

continuum_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} -t $(CONTINUUM_AGENT_TAG):$(CI_COMMIT_TAG) -f continuum/Dockerfile --push continuum

# Build all targets
all: node_agent cluster_agent continuum_agent
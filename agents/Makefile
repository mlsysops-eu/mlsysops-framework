# Variables
PLATFORMS := linux/amd64#,linux/arm64/v8

DOCKER_BUILDX=docker buildx build

# Default tags (can be overridden from CLI)
NODE_AGENT_TAG ?=  registry.mlsysops.eu/agent/agents/node
CLUSTER_AGENT_TAG ?= registry.mlsysops.eu/agent/agents/cluster
CONTINUUM_AGENT_TAG ?= registry.mlsysops.eu/agent/agents/continuum
TEST_APP_TAG ?= registry.mlsysops.eu/agent/agents/test_app
CI_COMMIT_TAG ?= 0.0.0

module:
	python3 -m build

node_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} --no-cache -t $(NODE_AGENT_TAG):$(CI_COMMIT_TAG) --push -f node/Dockerfile node

cluster_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} --no-cache -t $(CLUSTER_AGENT_TAG):$(CI_COMMIT_TAG) --push -f cluster/Dockerfile cluster

continuum_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} --no-cache -t $(CONTINUUM_AGENT_TAG):$(CI_COMMIT_TAG) --push -f continuum/Dockerfile continuum

test_application:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} --no-cache -t $(TEST_APP_TAG):$(CI_COMMIT_TAG) -f tests/application/Dockerfile --push tests/application
# Build all targets
all: node_agent cluster_agent continuum_agent
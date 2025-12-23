# Variables
PLATFORMS := linux/amd64,linux/arm64/v8

DOCKER_BUILDX=docker buildx build
#REGISTRY=registry.mlsysops.eu/aug-private/aug-uc
REGISTRY ?= harbor.nbfc.io/mlsysops
# Default tags (can be overridden from CLI)
NODE_AGENT_TAG ?= $(REGISTRY)/node-agent
CLUSTER_AGENT_TAG ?=$(REGISTRY)/cluster-agent
CONTINUUM_AGENT_TAG ?=$(REGISTRY)/continuum-agent
FITA_AGENT_TAG ?=$(REGISTRY)/fita-agent
TEST_APP_TAG ?=$(REGISTRY)/test_app
CI_COMMIT_TAG ?= 0.0.0

module:
	python3 -m build

node_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} -t $(NODE_AGENT_TAG):$(CI_COMMIT_TAG) --push -f node/Dockerfile .

cluster_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} -t $(CLUSTER_AGENT_TAG):$(CI_COMMIT_TAG) --push -f cluster/Dockerfile .

continuum_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} -t $(CONTINUUM_AGENT_TAG):$(CI_COMMIT_TAG) --push -f continuum/Dockerfile .

fita_agent:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} -t $(FITA_AGENT_TAG):$(CI_COMMIT_TAG) --push -f fita/Dockerfile .

test_application:
	$(DOCKER_BUILDX) --platform ${PLATFORMS} --no-cache -t $(TEST_APP_TAG):$(CI_COMMIT_TAG) -f tests/application/Dockerfile --push tests/application
# Build all targets
all: node_agent cluster_agent continuum_agent fita_agent
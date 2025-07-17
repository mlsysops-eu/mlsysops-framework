This document acts as a quickstart guide to showcase indicative features of the
`MLSysOps Framework`. Please refer to the [installation guide](../installation.md)
for more detailed installation instructions, or the
[design](../design#architecture) document for more details regarding
`MLSysOps`'s architecture.

## MLSysOps Framework Installation
The main prerequisite is that there is Karmada instance installed, with at least one Kubernetes cluster registered.
We assume that the Karmada is installed in a standalone cluster.
Karmada instance should include the `karmada-search` plugin.
You can follow the instructions in [Testbed installation](testbed.md) to create the appropriate environment.

MLSysOps Framework consists of three main components called MLSysOps Agents. These components require the following
services to operate before starting:

* Ejabberd XMPP Server
* Redis
* Docker installed in Karmada-Management VM

There are two services that provide additional functionalities to the user:

- **Northbound API**: This service is part of the MLSysOps agents. It provides endpoints for controlling the components and behaviors of the agents.
- **ML Connector**: This service is responsible for managing and deploying Machine Learning models. It exposes its functionality through a separate API.

To ensure the correct bootstrap, the agents should start in the following order:

1. Continuum agent
2. Cluster agent 
3. Node agents


All the deployments take place in a Kubernetes cluster, in separate namespace 'mlsysops-framework'. All the third-party services,
as well as the Continuum agent are deployed in the managament cluster, the same that is installed in karmada host.

#### Step 1: Clone the repo 

`git clone https://github.com/mlsysops-eu/mlsysops-framework`

and enter deployments directory 

`cd deployments`

#### Step 2: System descriptions preparation
Before the installation process takes place, system descriptions for every layer must be prepared.
A system description is a YAML file, implemented as Kubernetes CRDs.
Examples can be found in `descriptions/` directory.
The descriptions for each layer reside in the respectively named directory: continuum, clusters, nodes.
Each file MUST have the name of the corresponding hostname, followed by the .yaml or .yml suffix.
For example, a machine at the node level, with hostname `node-1`, should have a description file named `node-1.yaml` under
the directory `nodes/`.

* **Continuum** level descriptions, require one single file, that declare the continuumID and the clusters that we allow MLSysOps to manage.
* **Cluster** level descritptions, require a file for each cluster registered in Karmada. It contains the clusterID and a list of node hostnames, that MLSysOps is allowed to manage.
* **Node** level descriptions, contain the detailed information about the node resources. Example [here](descriptions/nodes/node-1.yaml).

Before deploying, prepare system descriptions as Kubernetes CRDs:

- Stored in the `descriptions/` directory

### 📁 File structure:

```
descriptions/
├── continuum/
│   └── <continuum-hostname>.yaml
├── clusters/
│   └── <cluster-hostname>.yaml
└── nodes/
    └── <node-hostname>.yaml
```

Descriptions define IDs, managed components, and resource details. All files are required before installation.

---

### Step 3: Deploy the Framework

There are two ways to deploy the framework:

#### Option 1: Automated using the MLSysOps CLI

You can install the CLI in two ways:

**From TestPyPI:**

```bash
pip install -i https://test.pypi.org/simple/ mlsysops-cli==0.1.9
```

**From GitHub (includes deployments folder):**

```bash
git clone https://github.com/marcolo-30/mlsysops-cli.git
cd mlsysops-cli
pip install -e .
```

This exposes the `mls` command.

**Set environment variables:**

```bash
export KARMADA_HOST_KUBECONFIG=<path to host kubeconfig>
export KARMADA_API_KUBECONFIG=<path to api kubeconfig>
export KARMADA_HOST_IP=<host IP>
```

**Run deployment:**

```bash
cd deployments/
mls framework deploy-all
```

This will:

- Deploy core services (ejabberd, redis, API service)
- Register system descriptions
- Deploy all agents in correct order

**Alternative:**
You can also run the CLI script directly:

```bash
cd deployments
python3 deploy.py
```

Wait for all pods to be created:

```bash
kubectl get pods -n mlsysops-framework
```

#### Option 2: Manual Deployment

Follow the order below to deploy manually if you prefer full control.

### Management Cluster (Continuum)

```bash
export KUBECONFIG=<host kubeconfig>
```

- Create namespace:
```bash
kubectl apply -f namespace.yaml
```

- Install services:
```bash
kubectl apply -f xmpp/deployment.yaml
kubectl apply -f api-service-deployment.yaml
kubectl apply -f redis-stack-deployment.yaml
```

- Start ML Connector:
```bash
docker compose -f mlconnector.docker-compose.yaml up -d
```

- Apply RBAC:
```bash
kubectl apply -f mlsysops-rbac.yaml
```

- Add configuration and system descriptions:
```bash
kubectl create configmap continuum-karmadapi-config --from-file=<karmada-api.kubeconfig> --namespace=mlsysops-framework
kubectl create configmap continuum-system-description --from-file=descriptions/continuum/<hostname>.yaml --namespace=mlsysops-framework
```

- Start the Continuum Agent:
```bash
kubectl apply -f continuum-agent-daemonset.yaml
```

### Karmada API Cluster (Cluster Agents)

```bash
export KUBECONFIG=<api kubeconfig>
```

- Apply policies and namespace:
```bash
kubectl apply -f cluster-propagation-policy.yaml
kubectl apply -f propagation-policy.yaml
kubectl apply -f namespace.yaml
kubectl apply -f mlsysops-rbac.yaml
```

- Add system descriptions:
```bash
kubectl create configmap cluster-system-description --from-file=descriptions/clusters --namespace=mlsysops-framework
```

- Start Cluster Agents:
```bash
kubectl apply -f cluster-agents-daemonset.yaml
```

### Node Agents

- Ensure node descriptions are in place
- Add them via ConfigMap:

```bash
kubectl create configmap node-system-descriptions --from-file=descriptions/nodes --namespace=mlsysops-framework
```

- Start Node Agents:

```bash
kubectl apply -f node-agents-daemonset.yaml
```

#### Step 4: Deploy a test application

We use a simple TCP Client - Server application, that send messages periodically. 
The files are in `tests/application` of the repo.

Update the `test_CR` and `test_MLSysOps_description`, with the node names of the cluster and the clusterID.

apply the CR:

`kubectl apply -f tests/application/test_CR.yaml`

or the description via the MLS CLI:

`cli/mls.py apps deploy-app --path tests/application/test_MLSysOps_descirption.yaml`

You can watch the pods starting and be managed by the MLSysOps Framework. The client pod will be
relocated every 30 seconds, with round-robin logic to every worker node.

`kubectl get pods -n mlsysops --context clusterID`

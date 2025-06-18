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

#### Step 2: Automated Deployment

MLSysOps CLI tool can be used to automatically deploy all the necessary components.
It needs the kubeconfigs of Karmada host cluster and Karmada API.

- `export KARMADA_HOST_KUBECONFIG=<path to karmada host kubeconfig>`
- `export KARMADA_API_KUBECONFIG=<path to karmada api kubeconfig>`
- `export KARMADA_HOST_IP=<karmada host ip>`

And then execute the CLI command inside `deployments` directory, with `descriptions` directory files prepared:
- `cd deployments`
- `python3 deploy.py`


Wait for the MLSysOps framework to be deployed, and you can check if the agents are running with: 

`kubectl get pods -n mlsysops-framework`

#### Step 4: Deploy a test application

We use a simple TCP Client - Server application, that send messages periodically. 
The files are in `tests/application` of the repo.

Update the test_CR and test_MLSysOps_description, with the node names of the cluster and the clusterID.

apply the CR:
`kubectl apply -f tests/application/test_CR.yaml`

or the description via the MLS CLI:

`cli/mls.py apps deploy-app --path tests/application/test_MLSysOps_descirption.yaml`

You can watch the pods starting and be managed by the MLSysOps Framework. The client pod will be
relocated every 30 seconds, with round-robin logic to every worker node.

`kubectl get pods -n mlsysops --context clusterID`

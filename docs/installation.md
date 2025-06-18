This document guides you through the installation of the `MLSysOps framework`
and all required components for executing all supported scenarios.

We assume a vanilla ubuntu 22.04 environment, although the `MLSysOps framework`
is able to run on a number of distros.

We will be installing and setting up each component individually:

### Core Framework

# MLSysOps Framework Installation
The main prerequisite is that there is Karmada instance installed, with at least one Kubernetes cluster registered.
We assume that the Karmada is installed in a standalone cluster.
Karmada instance should include the `karmada-search` plugin.

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


# System descriptions preparation
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

# Option 1: Automated Deployment

MLSysOps CLI tool can be used to automatically deploy all the necessary components.
It needs the kubeconfigs of Karmada host cluster and Karmada API.

- `export KARMADA_HOST_KUBECONFIG=<path to karmada host kubeconfig>`
- `export KARMADA_API_KUBECONFIG=<path to karmada api kubeconfig>`
- `export KARMADA_HOST_IP=<karmada host ip>`

And then execute the CLI command inside `deployments` directory, with `descriptions` directory files prepared:
- `python3 deploy.py`

# Option 2: Manual Deployment

## Continuum - Management Cluster
In Karmada host cluster: `export KUBECONFIG=<karmada host kubeconfig>`


- Create namespace
  - `kubectl apply -f namespace.yml`

- Install Required services
  - Change `POD_IP` to Karmada host IP in `xmpp/deployment.yaml`.
  - `kubectl apply -f xmpp/deployment.yaml`
  - Change `{{ KARMADA_HOST_IP }}` to Karmada host IP in `api-service-deployment.yaml`.
  - `kubectl apply -f api-service-deployment.yaml`
  - Change `{{ KARMADA_HOST_IP }}` to Karmada host IP in `redis-stack-deployment.yaml`.
  - `kubectpl apply -f redis-stack-deployment.yaml`
  - `docker compose up -d -f <mlconnector.docker-composer.yaml>`

- Apply RBAC
  - `kubectl apply -f mlsysops-rbac.yaml`

- Attach Karmada API kubeconfig as ConfigMap
  - `kubectl create configmap continuum-karmadapi-config --from-file=<path/to/local/karmada-api.kubeconfig> --namespace=mlsysops-framework`
- 
- Attach Continuum system description as ConfigMap
  - `kubectl create configmap continuum-system-description --from-file=<descriptions/continuum/hostname.yaml> --namespace=mlsysops-framework`

- Start continuum agent
  - `kubectl apply -f continuum-agent-daemonset.yaml`

---
In Karmada API Server: `export KUBECONFIG=<karmada api server kubeconfig>`

## Cluster deployments

- Setup Karmada propagation policies
  - `kubectl apply -f cluster-propagation-policy.yaml`
  - `kubectl apply -f propagation-policy.yaml`

- Create the namespace
  - `kubectl apply -f namespace.yaml`

- Apply RBAC
  - `kubectl apply -f mlsysops-rbac.yaml`

- Create a configmap based on the system description, using as the namefile, the hostname of the cluster manage node hostname
  - `kubectl create configmap cluster-system-description --from-file=descriptions/clusters --namespace=mlsysops-framework`

- Apply the daemonset YAML file
  - Change `{{ KARMADA_HOST_IP }}` to Karmada host IP in `cluster-agents-daemonset.yaml`. 
  - `kubectl apply -f cluster-agents-daemonset.yaml`

## Nodes deployment

- Namespaces and RBAC were created with the cluster setup.
- Prepare the system description, for each node, and name each file with the host name. 
- Create a configmap based on the system description, for each node.
  - `kubectl create configmap node-system-descriptions --from-file=descriptions/nodes --namespace=mlsysops-framework`
-  env variable.
- Apply the daemonset YAML file
  - `kubectl apply -f node-agents-daemonset.yaml`

> Note: Be aware that some instructions might override existing tools and services.


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
For example, a machine at the node level, with hostname `worker1`, should have a description file named `worker1.yaml` under
the directory `nodes/`.

* **Continuum** level descriptions, require one single file, that declare the continuumID and the clusters that we allow MLSysOps to manage.
* **Cluster** level descritptions, require a file for each cluster registered in Karmada. It contains the clusterID and a list of node hostnames, that MLSysOps is allowed to manage.
* **Node** level descriptions, contain the detailed information about the node resources. Example [here](descriptions/nodes/worker1.yaml).

# Automated Deployment

MLSysOps CLI tool can be used to automatically deploy all the necessary components.
It needs the kubeconfigs of Karmada host cluster and Karmada API.

- `export KARMADA_HOST_KUBECONFIG=<path to karmada host kubeconfig>`
- `export KARMADA_API_KUBECONFIG=<path to karmada api kubeconfig>`
- `export KARMADA_HOST_IP=<karmada host ip>`

And then execute the CLI command inside `deployments` directory, with `descriptions` directory files prepared:
- `python3 deploy.py`


#### Automatic system description generation
There is a python script that uses the content from `inventory.yaml` used in testbed installation steps.

- `python3 create_descriptions.py`

It reads the `inventory.yaml` in the same directory, and creates the yaml descriptions in the same directory. 
It also creates a test application description.


# Manual Deployment

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


## Test application

We use a simple TCP Client - Server application, that send messages periodically. 
The files are in repo/tests/application.

Update the test_CR and test_MLSysOps_description, with the node names of the cluster and the clusterID.

apply the CR or the descirption via the MLS CLI:
`kubectl apply -f tests/application/test_CR.yaml`

`mls.py apps deploy-app --path tests/application/test_MLSysOps_descirption.yaml`

## Custom Agent Configuration & Plugins

By default, each agent uses a default configuration and core policy plugins. 
Each agent, looks up to specific configmap for policies or configurations.


To change the agent configuration, override the following ConfigMap, **before** starting the corresponding agent level:

- `kubectl create configmap node-agents-config --from-file=<configurations/nodes> --namespace=mlsysops-framework`

To change the agent policy plugins, override the following ConfigMap, **at any time**.
Policy plugins reload dynamically (see [documentation](#)):
- `kubectl create configmap node-agents-config --from-file=<policy_plugins/nodes> --namespace=mlsysops-framework`



## Agent Environmental variables

| Variable Name                      | Values                                    | Description                                                                                                                          |
|------------------------------------|-------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| EJABBERD_DOMAIN                    | IP/domain                                 | The IP/domain of the continuum node used for spade agent login to xmpp (xmpp server ip), and from the cluster otel to send telemetry |
| MLS_OTEL_HIGHER_EXPORT             | ON (default)/OFF                          | Indicates if telemetry export to cluster/continuum OTEL is enabled. Used in cluster/node agents.                                     |
| MLS_OTEL_CLUSTER_PORT              | Port number (default 43170)               | The port used that cluster otel collector listens (gRPC)                                                                             |
| MLS_OTEL_CONTINUUM_PORT            | Port number                               | The continuum otel collector GRPC port. Must be set to cluster agent pod                                                             | 
| MLS_OTEL_PROMETHEUS_LISTEN_IP/PORT | IP:PORT                                   | The otel collector prometheus exporting ip/port, for every layer. For local fetch                                                    |
| MLS_OTEL_CONTINUUM_EXPORT_IP/PORT  | IP:PORT                                   | Used in continuum agent env pod if we want to use another OTEL collector receiving the telemetry stream                              |
| MLS_OTEL_MIMIR_EXPORT_ENDPOINT     | URL                                       | Used to indicate if the otel collector should export metrics to a mimir instance                                                     |
| MLS_OTEL_LOKI_EXPORT_ENDPOINT      | URL                                       | Used to indicate if the otel collector should export logs to a loki instance                                                         |
| MLS_OTEL_TEMPO_EXPORT_ENDPOINT     | URL                                       | Used to indicate if the otel collector should export traces to a tempo instance                                                      |
| MLS_OTEL_NODE_EXPORTER_FLAGS       | Comma-separated list (e.g. cpu,os,netdev) | Used to setup the --collect.* flags of node exporter. Always uses --collector.disable-defaults. Default: --collector.os              |
| LOCAL_OTEL_ENDPOINT                | IP                                        | The local IP                                                                                                                         |

### ML Connector
Use environmental variable MLS_MLCONNECTOR_ENDPOINT to provide the REST API URL:IP of the service. If none is provided, the object in
the policy will be None.
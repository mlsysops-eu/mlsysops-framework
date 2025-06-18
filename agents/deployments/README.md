# Deploy MLSysOps Framework Agents

Follow the steps by the following order:
1. Continuum agent setup
2. Cluster agent setup
3. Node agents setup

## Continuum

In karmada host cluster:

- Prerequisites: Install karmada with karmada-search enabled:
  - `sudo karmadactl --kubeconfig=/home/runner/karmada_management/karmada-host.kubeconfig addons enable karmada-search`
- Create the namespace
  - `kubectl apply -f namespace.yaml`

- Update the agent configuration file

- Upload the karmada api kubeconfig as ConfigMap
  - `kubectl create configmap continuum-config --from-file=path/to/local/file --namespace=mlsysops-framework`

- Apply RBAC
  - `kubectl apply -f mlsysops.rbac.yaml`

- Start XMPP server
  - `kubectl apply -f xmpp/confimap.yaml`
  - `kubectl apply -f xmpp/service.yaml`
  - `kubectl apply -f xmpp/deployment.yml`

- Start continuum agent
  - `kubectl apply -f continuum-agents-daemonset.yaml`

## Cluster

- Create the namespace
  - `kubectl apply -f namespace.yaml`

- -Apply RBAC
  - `kubectl apply -f mlsysops.rbac.yaml`

- Prepare the cluster system description YAML file.
- Create a configmap based on the system description, using as the namefile, the hostname of the cluster manage node hostname
  - `kubectl create configmap system-description --from-file=descriptions/<cluster-hostname>.yaml --namespace=mlsysops-framework`

- Update the agent configuration file
- Create a configmap based on the agent configuration YAML file.
  - `kubectl create configmap cluster-agent-config --from-file=configuration/cluster-config.yaml --namespace=mlsysops-framework`

- Apply the daemonset YAML file
  - `kubectl apply -f cluster-agent-daemonset.yaml`


## Node

1. Namespaces and RBAC were created with the cluster setup.

2. Prepare the system description, for each node, and name each file with the host name.
3. Create a configmap based on the system description, for each node.
`kubectl create configmap node-descriptions --from-file=descriptions/<node1-hostname>.yaml --from-file=descriptions/<node2-hostname>.yaml --namespace=mlsysops-framework`

4. Update the agent configuration file
5. Create a configmap based on the agent configuration YAML file.
`kubectl create configmap node-agent-config --from-file=configuration/<node1-hostname>.yaml --from-file=configuration/<node2-hostname>.yaml --namespace=mlsysops-framework`

5. Add the cluster node hostname to the CLUSTER env variable.

6. Apply the daemonset YAML file
`kubectl apply -f node-agents-daemonset.yaml`


## Test application

We use a simple TCP Client - Server application, that send messages periodically. 
The files are in repo/tests/application.

Update the test_CR and test_MLSysOps_description, with the node names of the cluster and the clusterID.

apply the CR or the descirption via the MLS CLI:
`kubectl apply -f tests/application/test_CR.yaml`

`mls.py apps deploy-app --path tests/application/test_MLSysOps_descirption.yaml`

## Custom Policies

Create a configmap based on each policy that you want to use inside the agents.
`kubectl create configmap cluster-policies --from-file=policy-<policy-name>.py --from-file=policy-<policy-name>.py --namespace=mlsysops-framework`




## Environmental variables

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

### ML Connect
Use environmental variable MLS_MLCONNECTOR_ENDPOINT to provide the REST API URL:IP of the service. If none is provided, the object in
the policy will be None.
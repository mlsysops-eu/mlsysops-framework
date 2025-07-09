**Note:** For more information about the type for each property refer to the corresponding CRD file.

# Application Custom Resource (`app.yaml`) Reference

This section provides a full example of the `app.yaml` custom resource along with a structured field reference table derived from the `MLSysOpsApplication.yaml` CRD. 
---

## Example `app.yaml`

```yaml
MLSysOpsApp:
  name: test-application
  cluster_placement:
    cluster_id: ["uth-prod-cluster"]
  components:
    - metadata:
        name: server-app
        uid: a9jwduj9028uje
      node_placement:
        continuum_layer:
          - edge
        node: node-1 # Replace with proper hostname
        mobile: True
      runtime_class_name: nvidia
      sensors:
        - camera:
            model: d455
            camera_type: rgb
            minimum_framerate: 20
            resolution: 1024x768
      restart_policy: OnFailure
      node_type: virtualized
      os: ubuntu
      container_runtime: containerd
      containers:
        - image: harbor.nbfc.io/mlsysops/test-app:latest
          platform_requirements:
            cpu: 
              requests: "250m"
              limits: "500m"
              architecture:
                - amd64
              frequency: 1.4
              performance_indicator: 30 # BogoMIPS
            memory:
              requests: "64Mi"
              limits: "128Mi"
            disk: "120"
          image_pull_policy: IfNotPresent
          command: ["python", "TcpServer.py"]
          env:
            - name: OTEL_RESOURCE_ATTRIBUTES
              value: "service.name=server-app, service.version=0.0.0, service.experimentid=test"
            - name: OTEL_SERVICE_NAME
              value: "server-app"
            - name: NODE_IP
              value_from:
                field_ref:
                  field_path: status.hostIP
            - name: TELEMETRY_ENDPOINT # Add code for this to be done dynamically
              value: "$(NODE_IP):43170"
            - name: TCP_SERVER_IP 
              value: "0.0.0.0"
          ports:
            - container_port: 10000
              protocol: TCP
      qos_metrics:
        - application_metric_id: test_received_success_counter
          target: 20
          relation: lower_or_equal
          system_metrics_hints:
            - cpu_frequency
      host_network: False
    - metadata:
        name: client-app
        uid: jdaddwewed235uje
      node_placement:
        mobile: False
        continuum_layer:
          - edge
      sensors:
        - temperature:
            model: sdc30
      restart_policy: OnFailure
      node_type: native
      os: ubuntu # Just for demonstration purposes.
      container_runtime: containerd
      containers:
        - image: harbor.nbfc.io/mlsysops/test-app:latest
          platform_requirements:
            cpu: #change to cpu and merge with resources above.
              requests: "250m"
              limits: "500m"
              architecture:
                - arm64
              frequency: 1.4
            memory:
              requests: "64Mi"
              limits: "128Mi"
            disk: "100"
            gpu:
              model: k80
              memory: 2
              performance_indicator: 320 # BogoMIPS
          image_pull_policy: IfNotPresent
          command: ["python", "TcpClient.py"]
          env:
            - name: OTEL_RESOURCE_ATTRIBUTES
              value: "service.name=server-app, service.version=0.0.0, service.experimentid=test"
            - name: OTEL_SERVICE_NAME
              value: "server-app"
            - name: NODE_IP
              value_from:
                field_ref:
                  field_path: status.hostIP
            - name: TELEMETRY_ENDPOINT
              value: "$(NODE_IP):43170"
            - name: TCP_SERVER_IP
              value: "server-app"
      qos_metrics:
        - application_metric_id: test_sent_success_counter
          target: 30
          relation: equal  
  component_interactions:
    - component_name1: client-app
      type: egress
      component_name2: server-app
  global_satisfaction:
    threshold: 0.7
    relation: greater_than
    achievement_weights:
      - metric_id: test_received_success_counter
        weight: 0.5
      - metric_id: test_sent_success_counter
        weight: 0.5

```

---

## Field Reference Table (Hierarchical View)

### Top-Level Fields

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `name` | The application name. | Yes | - |
| `cluster_placement.cluster_id` | Array of clusters that can host the application. | No | - |
| `components` | List of components of the application. | Yes | - |
| `component_interactions` | Describes how components communicate. | No | - |
| `global_satisfaction` | Global constraints for application satisfaction. | No | - |

### `components[].metadata`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `name` | The unique name of the component. | Yes | - |
| `uid` | Unique identifier (not user-defined). | Yes | - |

### `components[].node_placement`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `continuum_layer` | Required component placement on the continuum. | No | `cloud`, `far_edge`, `edge_infrastructure`, `edge`, `*` |
| `mobile` | Whether component is deployed on a mobile node. | No | `True`, `False` |
| `labels` | Required labels for filtering. | No | - |
| `node` | Required node name (optional). | No | - |

### `components[].sensors[]`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `camera.model` | Camera sensor model. | No | `d455`, `imx477`, `picamera-v2` |
| `camera.camera_type` | Type of camera sensor. | No | `rgb`, `nir`, `thermal`, `monocular` |
| `camera.minimum_framerate` | Minimum framerate. | No | - |
| `camera.resolution` | Camera resolution. | No | `1024x768`, `4056x3040` |
| `temperature.model` | Temperature sensor model. | No | `sdc30`, `ds18b20` |

### `components[].containers[]`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `image` | Name of the container image. | Yes | - |
| `command` | Container startup command. | No | - |
| `image_pull_policy` | Image pull policy. | No | `Always`, `Never`, `IfNotPresent` |

#### `components[].containers[].platform_requirements`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `cpu.requests` | CPU requests. | No | - |
| `cpu.limits` | CPU limits. | No | - |
| `cpu.architecture` | Supported architectures. | No | `arm64`, `amd64` |
| `cpu.frequency` | Required CPU frequency in Hz. | No | - |
| `cpu.performance_indicator` | CPU performance hint. | No | - |
| `memory.requests` | Memory requests. | No | - |
| `memory.limits` | Memory limits. | No | - |
| `disk` | Required disk space in GB. | No | - |
| `gpu.model` | GPU model. | No | `k80`, `k40` |
| `gpu.memory` | GPU memory in GB. | No | - |
| `gpu.performance_indicator` | GPU performance hint. | No | - |

#### `components[].containers[].ports[]`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `container_port` | Port exposed by the container. | No | (0, 65536) |
| `protocol` | Protocol for the port. | No | `UDP`, `TCP`, `SCTP` |

#### `components[].containers[].env[]`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `name` | Env variable name. | No | - |
| `value` | Env variable value. | No | - |
| `value_from.field_ref.field_path` | Reference to Kubernetes field. | No | - |


### `components[].qos_metrics[]`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `application_metric_id` | App metric id. | No | - |
| `target` | Metric target value. | No | - |
| `relation` | Desired relation (metric vs target). | No | `lower_or_equal`, `greater_or_equal`, `equal`, `lower_than`, `greater_than` |

### Other Component Fields

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `host_network` | Whether to use host network namespace. | No | `True`, `False` |
| `runtime_class_name` | Runtime class to use. | No | `nvidia`, `default`, `kata-fc`, `kata-dragon`, `urunc`, `crun`, `lunatic`, `nvidia-experimental`, `spin`, `wasmedge`, `slight` |
| `restart_policy` | Restart policy for the container. | No | `Always`, `OnFailure`, `Never` |
| `os` | Operating system type. | No | `ubuntu`, `kali`, `zephyr` |
| `node_type` | Type of the host node. | No | `virtualized`, `native`, `bare_metal` |
| `container_runtime` | Container runtime. | No | `containerd`, `docker`, `emb_serve` |


### `component_interactions[]`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `component_name1` | Source component. | No | - |
| `component_name2` | Destination component. | No | - |
| `type` | Type of interaction. | No | `ingress`, `egress` |

### `global_satisfaction`

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `threshold` | Minimum required satisfaction score. | No | [0.0, 1] |
| `relation` | Satisfaction comparison. | No | `greater_or_equal`, `equal`, `greater_than` |
| `achievement_weights[].metric_id` | Metric used for satisfaction. | No | - |
| `achievement_weights[].weight` | Weight of each metric (total weight sum must be 1). | No | - |


# Continuum, Cluster, and Node Custom Resources Reference

This documentation provides full example YAMLs and hierarchical field reference tables for the following custom resource definitions:

- `MLSysOpsContinuum`
- `MLSysOpsCluster`
- `MLSysOpsNode`

Each section includes:
- A sample YAML snippet.
- A structured table of fields with descriptions, required/optional status, and allowed values (if defined).

## MLSysOpsContinuum

### Example `continuum.yaml`

```yaml
MLSysOpsContinuum:
  name: demo-continuum
  continuum_id: demo-cont-id
  clusters:
    - uth-prod-cluster
```

### Field Reference Table

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `name` | The continuum slice name. | Yes | - |
| `continuum_id` | The unique continuum identifier. | Yes | - |
| `clusters` | The set of registered clusters. | Yes | - |
---

## MLSysOpsCluster

### Example `cluster.yaml`

```yaml
MLSysOpsCluster:
  name: uth-prod-cluster
  cluster_id: uth-prod-cluster
  nodes:
    - node-1
    - node-2
    - node-3
```

### Field Reference Table

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `name` | The cluster name. | Yes | - |
| `cluster_id` | The unique continuum identifier. | Yes | - |
| `nodes` | The set of registered nodes. | Yes | - |
---

## MLSysOpsNode

### Example `node.yaml`

```yaml
MLSysOpsNode:
  name: node-1
  labels:
    - gpu
    - edge-ready
  continuum_layer: edge
  cluster_id: uth-prod-cluster
  mobile: False
  location: [22.9576, 40.6401]  # [longitude, latitude] for stationary nodes
  sensors:
    - camera:
        model: d455
        camera_type: rgb
        framerate: 30
        supported_resolutions: ["1024x768"]
    - temperature:
        model: sdc30
  environment:
    node_type: virtualized
    os: ubuntu
    container_runtime: ["containerd"]
  hardware:
    cpu:
      model: Intel-i7
      architecture: amd64
      frequency: [2400000000, 3000000000]
      performance_indicator: 75 # BogoMIPS
    memory: 16
    disk: "256"
    gpu:
      model: k80
      memory: "4"
      performance_indicator: 100 
```
### Field Reference Table

| Field | Description | Required | Allowed Values |
|-------|-------------|----------|----------------|
| `name` | The name of the node. | No | - |
| `labels` | The required labels for filtering. | No | - |
| `continuum_layer` | Continuum placement level. | Yes | `cloud`, `edge_infrastructure`, `edge`, `far_edge` |
| `cluster_id` | The unique cluster identifier that the node reports to. | No | - |
| `mobile` | Specify if the node is mobile or stationary. | No | - |
| `location` | Geolocation coordinates (lon, lat). Valid only for stationary nodes. For mobile ones, the respective information is collected using telemetry. | No | - |
| `sensors[].camera.model` | The model name of the camera sensor. | No | `imx415`, `imx219`, `d455`, `imx477`, `picamera-v2` |
| `sensors[].camera.camera_type` | The camera sensor type. | No | - |
| `sensors[].camera.framerate` | Framerate. | No | - |
| `sensors[].camera.supported_resolutions` | Supported camera resolutions. | No | `1024x768`, `4056x3040` |
| `sensors[].temperature.model` | The model name of the temperature sensor. | No | `sdc30`, `ds18b20` |
| `environment.node_type` | Node type. | Yes | `virtualized`, `native`, `bare_metal` |
| `environment.os` | Operating system. | Yes | `ubuntu`, `kali`, `zephyr` |
| `environment.container_runtime[]` | Supported runtimes. | Yes | `containerd`, `docker`, `emb_serve` |
| `hardware.cpu.model` | CPU model name. | No | - |
| `hardware.cpu.architecture` | CPU architecture. | No | `amd64`, `arm64` |
| `hardware.cpu.frequency[]` | Possible CPU frequency values (Hz). | No | - |
| `hardware.cpu.performance_indicator` | Quantifies processing capabilities (BogoMIPS). | No | - |
| `hardware.memory` | Memory size (GB). | No | - |
| `hardware.disk` | Disk space (GB). | No | - |
| `hardware.gpu.model` | GPU model. | No | `k80`, `k40` |
| `hardware.gpu.memory` | GPU memory size. | No | - |
| `hardware.gpu.performance_indicator` | GPU performance score. | No | - |
---

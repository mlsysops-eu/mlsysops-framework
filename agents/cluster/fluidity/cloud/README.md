
# Fluidity control plane


## Packages used

* [Kubernetes client](https://github.com/kubernetes-client/python) Kubernetes API Python client
* [jsonschema](https://github.com/Julian/jsonschema) Python [JSON Schema](https://json-schema.org/) validator
* [ruamel.yaml](https://yaml.readthedocs.io) Python YAML 1.2 loader/dumper
* [Shapely](https://github.com/Toblerity/Shapely) Python package for manipulation and analysis of planar geometric objects
* [utm](https://github.com/Turbo87/utm) Python bidirectional UTM-WGS84 converter
* [Flask](http://flask.palletsprojects.com/) Python Web application framework
* [Flask-RESTX](https://flask-restx.readthedocs.io) Flask extension for building REST APIs
* [Werkzeug](https://werkzeug.palletsprojects.com/en/2.0.x/) WSGI web utility library


## Installation

* Install [docker](https://docs.docker.com/get-docker/) and [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)

* Instal [k3d](https://k3d.io) to run [k3s](https://k3s.io/) clusters:
```bash
wget -q -O - https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
```

* Install Kubernetes API [Python client](https://github.com/kubernetes-client/python) for interacting with cluster resources:
```bash
pip3 install kubernetes
```
or from source:
```bash
git clone --recursive https://github.com/kubernetes-client/python.git
cd python
python setup.py install
```

* Install [jsonschema](https://github.com/Julian/jsonschema) and [ruamel.yaml](https://yaml.readthedocs.io) for the validation of Fluidity-related resources and the interaction with YAML files:
```bash
pip3 install jsonschema
pip3 install ruamel.yaml
```

* Install [Shapely](https://github.com/Toblerity/Shapely) and [utm](https://github.com/Turbo87/utm) for geographic-related conversions and manipulations:
```bash
pip3 install shapely
pip3 install utm
```

* Install [Flask](http://flask.palletsprojects.com/), [Flask-RESTX](https://flask-restx.readthedocs.io) and [Werkzeug](https://werkzeug.palletsprojects.com/en/2.0.x/) for interacting with Fluidity-related cluster resources through a REST API and the [Swagger UI](https://swagger.io/tools/swagger-ui/) documentation:
```bash
pip3 install flask
pip3 install flask-restx
# pip3 install Werkzeug==0.16.0 # pin version to fix problem
```

## Cluster configuration

* Create cluster:
```bash
# Create cluster with a single server, two worker nodes and without load balancer
k3d cluster create fluiditybasic --no-lb --servers 1 --agents 2

# Check cluster creation
k3d cluster list
NAME              SERVERS   AGENTS   LOADBALANCER
fluiditybasic      1/1       2/2      false

# Check created nodes
kubectl get nodes
NAME                        STATUS   ROLES                  AGE    VERSION
k3d-fluiditybasic-agent-1    Ready    <none>                 83s    v1.21.1+k3s1
k3d-fluiditybasic-server-0   Ready    control-plane,master   100s   v1.21.1+k3s1
k3d-fluiditybasic-agent-0    Ready    <none>                 93s    v1.21.1+k3s1
```

* Register Fluidity CRDs. From the `resources/crds/` directory, run:
```bash
./crds_register.sh
```

* Create the fluidity node agents container images. From the `node/` directory, run:
```bash
docker build -t fluidity/fluidity-agent-e0-img:latest -f Dockerfile.e0 .
docker build -t fluidity/fluidity-agent-e1-img:latest -f Dockerfile.e1 .
docker build -t fluidity/fluidity-agent-c0-img:latest -f Dockerfile.c0 .
```

* Create camera service container image. From the `system_services/camera/` directory, run:
```bash
docker build -t fluidity/camera-service-e0-img -f Dockerfile.pc .
```
Depending of the service installation (RPi/PC, drone/static node etc.) the  corresponding picamera_controller* has to be imported in the `camera_server.py`. In addition, for static nodes the respective coordinates have to be set at the `camera_setting.py` before building the image.


* Make the node agent and service container image available to the cluster's registry:
```bash
k3d image import fluidity/fluidity-agent-e0-img:latest -c fluiditybasic
k3d image import fluidity/fluidity-agent-e1-img:latest -c fluiditybasic
k3d image import fluidity/fluidity-agent-c0-img:latest -c fluiditybasic
k3d image import fluidity/camera-service-e0-img:latest -c fluiditybasic
```

* Similarly, create the container images for the application components. From `apps/basic/ground-viewer/`, run:
```bash
docker build -t fluidity/ground-viewer-basic-img .
```
There is also a mockup implementation of the component in `apps/basic/ground-viewer-mu/` where it does not actually invoke the camera service.

Then, from `apps/basic/image-checker/` run:
```bash
docker build -t fluidity/image-checker-basic-img .
```

* Make the application component container images available to cluster nodes:
```bash
k3d image import fluidity/ground-viewer-basic-img:latest -c fluiditybasic
# k3d image import fluidity/ground-viewer-basic-mu-img:latest -c fluiditybasic
k3d image import fluidity/image-checker-basic-img:latest -c fluiditybasic
```

* Give rights to agent pods to read/update required resources and deploy fluidity node agents. From the `node/` directory, run:
```bash
kubectl apply -f fluidity_agent_rbac.yaml
kubectl apply -f pod-agent-c0.yaml
kubectl apply -f pod-agent-e0.yaml
kubectl apply -f pod-agent-e1.yaml
```
`NOTE`: In k3s worker nodes of a cluster are called agents. This should not be confused with the fluidity node agents that submit the node description in the cluster and set some specific labels.

* Deploy camera service at k3d-fluiditybasic-agent-0 node. From the `resources/manifests/basic-app/` directory, run:
```bash
kubectl apply -f pod-cam-server-e0.yaml
```

* Start the FluidityApp controller. From the `cloud/` directory, run:
```bash
$ python fluidityapp_controller.py
....
[2022-04-30 10:44:27,628] INFO [fluidityapp_controller.py] AppHandler thread started
```

* Submit the basic-app application for deployment. From the `resources/manifests/basic-app/` directory, run:
```bash
kubectl apply -f basic-app.yaml
```

* In the FluidityApp controller console you should see an output similar to the following:
```bash
...
[2022-04-30 10:44:27,635] INFO [fluidityapp_controller.py] Handling ADDED on basic-app
[2022-04-30 10:44:27,636] INFO [fluidityapp_controller.py] New app: basic-app - not in apps_dict
[2022-04-30 10:44:27,636] INFO [fluidityapp_controller.py] Add FluidityApp basic-app
...
[2022-04-30 10:44:27,860] INFO [fluidityapp_deploy.py] Deploy Pods for components of app: basic-app
[2022-04-30 10:44:28,486] INFO [fluidityapp_monitor.py] AppMonitor basic-app started
[2022-04-30 10:44:28,495] INFO [fluidityapp_monitor.py] ground-viewer-el0-x7x7 status: Pending
[2022-04-30 10:44:28,501] INFO [fluidityapp_monitor.py] image-checker-c-kcql status: Pending
[2022-04-30 10:44:33,517] INFO [fluidityapp_monitor.py] ground-viewer-el0-x7x7 status: Running
[2022-04-30 10:44:33,524] INFO [fluidityapp_monitor.py] image-checker-c-kcql status: Running
```
* Inspect container logs:
```bash
# Check docker containers representing cluster nodes
$ docker ps
CONTAINER ID   IMAGE                      COMMAND                  CREATED        STATUS        PORTS                     NAMES
2c46cc6c1c8c   rancher/k3s:v1.21.1-k3s1   "/bin/k3s agent"         18 hours ago   Up 18 hours                             k3d-fluiditybasic-agent-1
42fed922fe75   rancher/k3s:v1.21.1-k3s1   "/bin/k3s agent"         18 hours ago   Up 18 hours                             k3d-fluiditybasic-agent-0
6d73451c13b8   rancher/k3s:v1.21.1-k3s1   "/bin/k3s server --t…"   18 hours ago   Up 18 hours   0.0.0.0:38161->6443/tcp   k3d-fluiditybasic-server-0

# Get command line to a node
$ docker exec -it k3d-fluiditybasic-agent-0 /bin/sh

# Check running containers
$ crictl ps
CONTAINER           IMAGE               CREATED             STATE               NAME                ATTEMPT             POD ID
81b5a5288c6d9       fd0a2f91d5a49       2 hours ago         Running             ground-viewer       0                   31329787a2f75
93132e878aa6d       3c5ac995e758d       12 hours ago        Running             camera-server       0                   12750ea89a016
...
```
For more info regarding crictl, check [crictl README](https://github.com/kubernetes-sigs/cri-tools/blob/master/docs/crictl.md) and [mapping dockercli to crictl](https://kubernetes.io/docs/reference/tools/map-crictl-dockercli/)


* Alternatively, monitor service and component logs using kubectl:
```bash
# Camera server
$ kubectl logs camera-server-k3d-fluiditybasic-agent-0 -c camera-server --tail 1 --follow
...
[2022-04-30 07:47:51,367] DEBUG [policy_checker.py] Check has access: 4ad11d25-041f-455d-a87f-9a56e59ba05b.ground-viewer-el0-x7x7 @ /CameraService/CaptureImage
[2022-04-30 07:47:51,783] DEBUG [policy_checker.py] Check has access: 4ad11d25-041f-455d-a87f-9a56e59ba05b.ground-viewer-el0-x7x7 @ /CameraService/RetrieveImage
...

# GroundViewer
$ kubectl logs ground-viewer-el0-x7x7 -c ground-viewer --tail 1 --follow
...
[2022-04-30 07:49:52,129] INFO [ground_viewer.py] Image retrieved: IMG_220430_074949.jpg
[2022-04-30 07:49:52,139] INFO [ground_viewer.py] Image sent
{'msg': 'success'}
...

# ImageChecker
$ kubectl logs image-checker-c-kcql -c image-checke --tail 1 --follow
...
[2022-04-30 07:49:52,138] INFO [_internal.py] 10.42.1.0 - - [30/Apr/2022 07:49:52] "POST /img_bin HTTP/1.1" 200 -
...
```

Also, see [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/).

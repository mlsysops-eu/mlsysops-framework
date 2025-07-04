from pathlib import Path
from importlib.resources import files
import kubernetes.client.rest
import yaml
from jinja2 import Environment, FileSystemLoader
from kubernetes import client, config
from kubernetes.client import ApiException
from ruamel.yaml import YAML
import os
from jinja2 import Template
import subprocess
from mlsysops_cli import deployment
from mlsysops_cli.deployment.descriptions_util import create_cluster_yaml, create_worker_node_yaml,create_continuum_yaml


def parse_yaml_from_file(path_obj: Path, template_variables: dict = {}) -> list | None:
    """
    Parses a YAML file from a Path object (e.g. importlib.resources.files(...)) using Jinja2 templates
    to dynamically substitute values, then manages and sorts multiple resource definitions.

    Parameters:
        path_obj: Path
            A Path object pointing to the YAML file to parse.
        template_variables: dict
            Variables to substitute in the Jinja2 template.

    Returns:
        list | None
            A sorted list of parsed Kubernetes resource definitions or None if the file is empty or missing.
    """
    yaml = YAML(typ='safe')

    if not path_obj.exists():
        print(f"❌ File does not exist: {path_obj}")
        return None

    raw_template = path_obj.read_text(encoding="utf-8")
    template = Template(raw_template)
    rendered_template = template.render(**template_variables)
    resources = list(yaml.load_all(rendered_template))

    if not resources:
        print(f"⚠️ No resources found in file: {path_obj}")
        return None

    resource_order = [
        "namespace", "serviceaccount", "clusterrole", "rolebinding", "clusterrolebinding",
        "configmap", "secret", "persistentvolumeclaim", "service", "deployment", "daemonset"
    ]

    sorted_resources = sorted(
        resources,
        key=lambda r: resource_order.index(r["kind"].lower()) if r["kind"].lower() in resource_order else len(resource_order)
    )

    return sorted_resources

def apply_kubeconfig(config_path, file_to_apply):
    try:
        # Construct the kubectl command
        command = ["/usr/local/bin/kubectl", "apply", "-f", file_to_apply]
        env = {"KUBECONFIG": config_path}

        # Execute the command
        result = subprocess.run(command, env=env, check=True, text=True, capture_output=True)

        # Print the output of the command
        print("Command succeeded. Output:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Command failed. Error:")
        print(e.stderr)


def get_method(kind, operation):
    """
    Retrieves the method corresponding to a Kubernetes resource kind and operation. This function maps a
    given resource kind (e.g., 'service', 'secret', 'deployment') and an operation (e.g., 'read', 'create',
    'delete', 'replace') to the appropriate method provided by the Kubernetes Python client library.
    It ensures that only supported kinds and operations are used.

    Parameters:
        kind: str
            The type of Kubernetes resource. Examples include 'service', 'namespace', 'deployment', etc.
        operation: str
            The desired operation to perform on the resource. Examples include 'read', 'create',
            'replace', and 'delete'.

    Returns:
        Callable
            A callable method corresponding to the provided kind and operation.

    Raises:
        Exception
            If the provided kind or operation is unsupported.
    """
    kind_to_method = {
        "service": {
            "read": client.CoreV1Api().read_namespaced_service,
            "replace": client.CoreV1Api().replace_namespaced_service,
            "delete": client.CoreV1Api().delete_namespaced_service,
            "create": client.CoreV1Api().create_namespaced_service,
        },
        "secret": {
            "read": client.CoreV1Api().read_namespaced_secret,
            "replace": client.CoreV1Api().replace_namespaced_secret,
            "delete": client.CoreV1Api().delete_namespaced_secret,
            "create": client.CoreV1Api().create_namespaced_secret,
        },
        "configmap": {
            "read": client.CoreV1Api().read_namespaced_config_map,
            "replace": client.CoreV1Api().replace_namespaced_config_map,
            "delete": client.CoreV1Api().delete_namespaced_config_map,
            "create": client.CoreV1Api().create_namespaced_config_map,
        },
        "persistentvolumeclaim": {
            "read": client.CoreV1Api().read_namespaced_persistent_volume_claim,
            "replace": client.CoreV1Api().replace_namespaced_persistent_volume_claim,
            "delete": client.CoreV1Api().delete_namespaced_persistent_volume_claim,
            "create": client.CoreV1Api().create_namespaced_persistent_volume_claim,
        },
        "deployment": {
            "read": client.AppsV1Api().read_namespaced_deployment,
            "replace": client.AppsV1Api().replace_namespaced_deployment,
            "delete": client.AppsV1Api().delete_namespaced_deployment,
            "create": client.AppsV1Api().create_namespaced_deployment,
        },
        "daemonset": {
            "read": client.AppsV1Api().read_namespaced_daemon_set,
            "replace": client.AppsV1Api().replace_namespaced_daemon_set,
            "delete": client.AppsV1Api().delete_namespaced_daemon_set,
            "create": client.AppsV1Api().create_namespaced_daemon_set,
        },
        "namespace": {
            "read": client.CoreV1Api().read_namespace,
            "replace": client.CoreV1Api().replace_namespace,
            "delete": client.CoreV1Api().delete_namespace,
            "create": client.CoreV1Api().create_namespace,
        },
        "serviceaccount": {
            "read": client.CoreV1Api().read_namespaced_service_account,
            "replace": client.CoreV1Api().replace_namespaced_service_account,
            "delete": client.CoreV1Api().delete_namespaced_service_account,
            "create": client.CoreV1Api().create_namespaced_service_account,
        },
        "rolebinding": {
            "read": client.RbacAuthorizationV1Api().read_namespaced_role_binding,
            "replace": client.RbacAuthorizationV1Api().replace_namespaced_role_binding,
            "delete": client.RbacAuthorizationV1Api().delete_namespaced_role_binding,
            "create": client.RbacAuthorizationV1Api().create_namespaced_role_binding,
        },
        "clusterrole": {
            "read": client.RbacAuthorizationV1Api().read_cluster_role,
            "replace": client.RbacAuthorizationV1Api().replace_cluster_role,
            "delete": client.RbacAuthorizationV1Api().delete_cluster_role,
            "create": client.RbacAuthorizationV1Api().create_cluster_role,
        },
        "clusterrolebinding": {
            "read": client.RbacAuthorizationV1Api().read_cluster_role_binding,
            "replace": client.RbacAuthorizationV1Api().replace_cluster_role_binding,
            "delete": client.RbacAuthorizationV1Api().delete_cluster_role_binding,
            "create": client.RbacAuthorizationV1Api().create_cluster_role_binding,
        }
    }

    if kind not in kind_to_method:
        raise Exception(f"Unsupported kind: {kind}")

    if operation not in kind_to_method[kind]:
        raise Exception(f"Unsupported operation: {operation}")

    return kind_to_method[kind][operation]


class KubernetesLibrary:
    core_v1_api = None
    apps_v1_api = None
    custom_objects_api = None
    group = None
    version = None


    def __init__(self, group=None, version=None, kubeconfig=None, context=None):
        """
        Initialize Kubernetes configuration, custom objects API, core v1 API, and apps v1 API.

        :param group: API group (e.g., 'apps').
        :param version: API version (e.g., 'v1').
        :param kubeconfig: Path to the kubeconfig file.
        :param context: Specific context to load from the kubeconfig file.
        """

        # Load Kubernetes configuration for the specified environment and context
        if kubeconfig:
            print(f"Loading kubeconfig from {kubeconfig}, context: {context}")
            config.load_kube_config(config_file=kubeconfig, context=context)
        elif 'KUBERNETES_PORT' in os.environ:
            print("Loading in-cluster Kubernetes configuration")
            config.load_incluster_config()
        else:
            print(f"Loading default kubeconfig, context: {context}")
            config.load_kube_config(context=context)

        print(f"Kubernetes configuration loaded successfully")
        self.group = group
        self.version = version
        self.custom_objects_api = client.CustomObjectsApi()
        self.core_v1_api = client.CoreV1Api()
        self.apps_v1_api = client.AppsV1Api()

    def create_custom_object(self, yaml_content):
        kind = yaml_content["kind"]

        try:
            self.custom_objects_api.create_namespaced_custom_object(
                group=self.group,
                version=self.version,
                namespace=self.namespace,
                plural=kind.lower() + "s",
                body=yaml_content,
            )
        except ApiException as e:
            print(f"Failed to apply kind '{yaml_content['kind']}' to Kubernetes API: {e}")

    def update_custom_object(self, name, yaml_content):
        kind = yaml_content["kind"]

        try:
            self.custom_objects_api.replace_namespaced_custom_object(
                group=self.group,
                version=self.version,
                namespace=self.namespace,
                plural=kind.lower() + "s",
                name=name,
                body=yaml_content,
            )
        except ApiException as e:
            print(f"Failed to apply kind '{yaml_content['kind']}' to Kuberentes API: {e}")

    def create_or_update(self, resource_yaml):

        try:

            kind = resource_yaml["kind"].lower()
            name = resource_yaml["metadata"].get("name", "None")
            namespace = resource_yaml["metadata"].get("namespace")
            print(f"Creating/Updating resource: {name} of kind {kind} in namespace {namespace} ")
            if namespace is not None:
                existing_resource = get_method(kind, "read")(name, namespace=namespace)
                get_method(kind, "replace")(name=name, namespace=namespace, body=resource_yaml)

            else:
                existing_resource = get_method(kind, "read")(name)
                get_method(kind, "replace")(name=name, body=resource_yaml)

                print(f"Updated resource: {name}")
        except KeyError as e:
            print(f"Error parsing resource: {e}")
            return
        except client.exceptions.ApiException as e:
            if e.status == 404:
                print(f"Resource '{name}' of kind '{kind}' not found. Creating it now. {namespace}")
                if namespace is not None:
                    if kind in ['serviceaccount', 'configmap', 'daemonset', "deployment", "service",
                                "persistentvolumeclaim"]:
                        get_method(kind, "create")(namespace=namespace, body=resource_yaml)

                    else:
                        get_method(kind, "create")(name=name, namespace=namespace, body=resource_yaml)
                else:
                    get_method(kind, "create")(body=resource_yaml)
            else:
                print(f"Error updating Service '{name}' in namespace '{namespace}': {e}")

    def create_configmap_from_file(self, descriptions_directory, namespace, name, suffixes=["*.yml", "*.yaml"]):
        """
        Create a ConfigMap from all YAML files inside a given folder inside the package.
        """
        files_data_object = {}
        directory = Path(descriptions_directory)
        try:
            for suffix in suffixes:
                for file in directory.glob(suffix):
                    print(f"Reading file: {file.name}")
                    file_data = file.read_text()
                    files_data_object[file.name] = file_data
        except Exception as e:
            print(f"Error reading from {descriptions_directory}: {e}")
            return

        config_map = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=name, namespace=namespace),
            data=files_data_object
        )

        try:
            self.core_v1_api.create_namespaced_config_map(namespace, config_map)
            print(f"✅ Created configmap {name}")
        except ApiException as e:
            if e.status != 409:
                self.core_v1_api.replace_namespaced_config_map(name, namespace, config_map)
                print(f"♻️ Updated configmap {name}")

    def get_karmada_clusters(self):
        """
        Retrieve the clusters registered in Karmada, replicating 'kubectl get clusters'.

        :return: A list of cluster names and their details.
        """
        try:
            # Query the 'clusters' custom resource in the 'clusters.karmada.io' API group
            group = "cluster.karmada.io"
            version = "v1alpha1"
            plural = "clusters"

            response = self.custom_objects_api.list_cluster_custom_object(
                group=group,
                version=version,
                plural=plural
            )

            # Process the response to extract cluster names and details
            clusters = []
            for item in response.get("items", []):
                clusters.append({
                    "name": item["metadata"]["name"],
                    "status": item.get("status", {}).get("conditions", "Unknown")
                })

            return_object = {}
            for cluster in clusters:
                return_object[cluster['name']] = cluster['status'][0]['status']
            return return_object

        except Exception as e:
            print(f"Error retrieving clusters: {e}")
            return []

    def apply_karmada_policy(self, policy_name: str, policy_body: dict, plural: str, namespaced: bool = False,
                             namespace: str = None):
        """
        Apply or update a resource in Karmada.

        Handles both namespaced and cluster-scoped resources.

        :param policy_name: The name of the resource (used for identification).
        :param policy_body: The body of the resource as a Python dictionary.
        :param plural: The plural name of the resource (e.g., "propagationpolicies" or "clusterpropagationpolicies").
        :param namespaced: Whether the resource is namespaced (True) or cluster-scoped (False).
        :param namespace: The namespace to target for namespaced resources (required if namespaced=True).
        """
        try:

            # Define API group and version (specific to Karmada policies)
            group = "policy.karmada.io"
            version = "v1alpha1"

            print(
                f"Applying resource '{policy_name}' with group: {group}, version: {version}, plural: {plural}, namespaced: {namespaced}"
            )

            if namespaced and not namespace:
                raise ValueError("Namespace must be provided for namespaced resources.")

            try:
                if namespaced:
                    # Fetch the current resource in the given namespace
                    current_resource = self.custom_objects_api.get_namespaced_custom_object(
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=plural,
                        name=policy_name
                    )
                else:
                    # Fetch the current cluster-scoped resource
                    current_resource = self.custom_objects_api.get_cluster_custom_object(
                        group=group,
                        version=version,
                        plural=plural,
                        name=policy_name
                    )

                # Add the required resourceVersion field to the policy body
                resource_version = current_resource["metadata"]["resourceVersion"]
                policy_body["metadata"]["resourceVersion"] = resource_version

                print(f"Resource '{policy_name}' exists. Updating it...")

                # Perform an update using replace
                if namespaced:
                    self.custom_objects_api.replace_namespaced_custom_object(
                        group=group,
                        version=version,
                        namespace=namespace,
                        plural=plural,
                        name=policy_name,
                        body=policy_body
                    )
                else:
                    self.custom_objects_api.replace_cluster_custom_object(
                        group=group,
                        version=version,
                        plural=plural,
                        name=policy_name,
                        body=policy_body
                    )
                print(f"Resource '{policy_name}' updated successfully.")

            except ApiException as e:
                if e.status == 404:
                    # If the resource doesn't exist, create a new one
                    print(f"Resource '{policy_name}' not found. Creating a new one...")

                    # Create the new resource
                    if namespaced:
                        self.custom_objects_api.create_namespaced_custom_object(
                            group=group,
                            version=version,
                            namespace=namespace,
                            plural=plural,
                            body=policy_body
                        )
                    else:
                        self.custom_objects_api.create_cluster_custom_object(
                            group=group,
                            version=version,
                            plural=plural,
                            body=policy_body
                        )
                    print(f"New resource '{policy_name}' created successfully.")
            else:
                raise  # Re-raise any non-404 exceptions

        except Exception as e:
            print(f"Error applying resource '{policy_name}': {e}")

    def apply_mlsysops_propagation_policies(self):
        """
        Dynamically generate and apply a PropagationPolicy using the active clusters from self.clusters.
        """
        try:
            # Extract cluster names where the cluster status is True (ready)
            cluster_names = [name for name, status in self.get_karmada_clusters().items() if status.lower() == 'true']

            print(f"Applying PropagationPolicy with cluster names: {cluster_names}")

            # Correctly load template path using importlib.resources
            templates_path = str(files(deployment))
            env = Environment(loader=FileSystemLoader(templates_path))  # Uses actual package folder

            # Apply Cluster-Wide PropagationPolicy
            try:
                name = "mlsysops-cluster-propagation-policy"
                cluster_template = env.get_template("cluster-propagation-policy.yaml")
                rendered_cluster_policy = cluster_template.render(name=name, cluster_names=cluster_names)

                yaml = YAML(typ='safe')
                cluster_policy_body = yaml.load(rendered_cluster_policy)

                self.apply_karmada_policy(
                    policy_name=name,
                    policy_body=cluster_policy_body,
                    plural="clusterpropagationpolicies",
                    namespaced=False,
                )
                print(f"✅ Cluster-Wide PropagationPolicy applied.")

            except Exception as e:
                print(f"❌ Error applying Cluster-Wide PropagationPolicy: {e}")

            # Apply Simple PropagationPolicy
            try:
                name = "mlsysops-propagate-policy"
                simple_template = env.get_template("propagation-policy.yaml")
                rendered_simple_policy = simple_template.render(name=name, cluster_names=cluster_names)

                yaml = YAML(typ='safe')
                simple_policy_body = yaml.load(rendered_simple_policy)

                self.apply_karmada_policy(
                    policy_name=name,
                    policy_body=simple_policy_body,
                    plural="propagationpolicies",
                    namespaced=True,
                    namespace="default"
                )
                print(f"✅ Simple PropagationPolicy applied.")

            except Exception as e:
                print(f"❌ Error applying Simple PropagationPolicy: {e}")

        except Exception as e:
            print(f"❌ Error applying PropagationPolicies: {e}")

def _check_required_env_vars(*required_vars):
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

def run_deploy_all(path, inventory_path):
    try:
        print("🚀 Deploying all MLSysOps components...")
        deploy_core_services()
        deploy_continuum_agents(path, inventory_path)
        deploy_cluster_agents(path, inventory_path)
        deploy_node_agents(path, inventory_path)
        print("✅ All components deployed successfully.")
    except Exception as e:
        print(f"❌ Error in deploy_all: {e}")
        raise
    # Create Karmada objects - load the client with the Karmada host kubeconfig
    kubernetes_client = KubernetesLibrary("apps", "v1",
                                          kubeconfig=os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
                                          context="karmada-host")

    # Create or update the namespace, RBAC, and service account for the MLSAgent
    namespace_resources = kubernetes_client.parse_yaml("namespace.yaml")
    for resource in namespace_resources:
        kubernetes_client.create_or_update(resource)
    #
    rbac_resources = kubernetes_client.parse_yaml("mlsysops-rbac.yaml")
    for resource in rbac_resources:
        kubernetes_client.create_or_update(resource)

def deploy_core_services():
    print("🔧 Deploying core services (ejabberd, redis, API service)...")
    _check_required_env_vars("KARMADA_HOST_IP", "KARMADA_HOST_KUBECONFIG")
    client_k8s = KubernetesLibrary("apps", "v1", os.getenv("KARMADA_HOST_KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"))
    _apply_namespace_and_rbac(client_k8s)

    # Ruta al archivo xmpp/deployment.yaml
    xmpp_path = files(deployment).joinpath("xmpp/deployment.yaml")
    for r in parse_yaml_from_file(xmpp_path, {"POD_IP": os.getenv("KARMADA_HOST_IP")}):
        client_k8s.create_or_update(r)

    # Ruta al archivo api-service-deployment.yaml
    api_path = files(deployment).joinpath("api-service-deployment.yaml")
    for r in parse_yaml_from_file(api_path, {"KARMADA_HOST_IP": os.getenv("KARMADA_HOST_IP")}):
        client_k8s.create_or_update(r)

    # Ruta al archivo redis-stack-deployment.yaml
    redis_path = files(deployment).joinpath("redis-stack-deployment.yaml")
    for r in parse_yaml_from_file(redis_path, {"KARMADA_HOST_IP": os.getenv("KARMADA_HOST_IP")}):
        client_k8s.create_or_update(r)
    # Load continuum agent configmaps
    kubernetes_client.create_configmap_from_file("descriptions/continuum",
                                                 "mlsysops-framework",
                                                 "continuum-system-description")

    kubernetes_client.create_configmap_from_file("descriptions/continuum",
                                                 "mlsysops-framework",
                                                 "continuum-karmadapi-config",
                                                 suffixes=["*.kubeconfig"])

def deploy_continuum_agents(path, inventory_path):
    print("🧠 Deploying Continuum Agent...")
    _check_required_env_vars("KARMADA_HOST_IP", "KARMADA_HOST_KUBECONFIG")
    client_k8s = KubernetesLibrary("apps", "v1", os.getenv("KARMADA_HOST_KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"))
    _apply_namespace_and_rbac(client_k8s)

    descriptions_path = os.getenv("CONTINUUM_SYSTEM_DESCRIPTIONS_PATH", "descriptions")
    if path:
        descriptions_path = path

    if inventory_path:
        # build the system descriptions
        parent_dir = "descriptions"
        descriptions_path = os.path.join(parent_dir, "continuum")
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
        if not os.path.exists(descriptions_path):
            os.makedirs(descriptions_path)


        create_continuum_yaml(inventory_path, descriptions_path)

    # ConfigMap descriptions
    client_k8s.create_configmap_from_file(descriptions_path, "mlsysops-framework", "continuum-system-description")
    ## Cluster agent deployment
    karmada_api_client = KubernetesLibrary("apps", "v1",
                                          kubeconfig=os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
                                          context="karmada-apiserver")

    kubeconfig_path = files(deployment).joinpath("descriptions/continuum")
    client_k8s.create_configmap_from_file(kubeconfig_path, "mlsysops-framework", "continuum-karmadapi-config", suffixes=["*.kubeconfig"])

    # DaemonSet YAML
    daemonset_path = files(deployment).joinpath("continuum-agent-daemonset.yaml")
    for r in parse_yaml_from_file(daemonset_path):
        client_k8s.create_or_update(r)

def deploy_cluster_agents(path, inventory_path):
    print("🏢 Deploying Cluster Agents...")
    _check_required_env_vars("KARMADA_HOST_IP", "KARMADA_API_KUBECONFIG")
    client_karmada = KubernetesLibrary("apps", "v1", os.getenv("KARMADA_API_KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"))
    _apply_namespace_and_rbac(client_karmada)
    client_karmada.apply_mlsysops_propagation_policies()

    descriptions_path = os.getenv("CLUSTER_SYSTEM_DESCRIPTIONS_PATH", "descriptions")
    if path:
        descriptions_path = path

    if inventory_path:
        # build the system descriptions
        parent_dir = "descriptions"
        descriptions_path = os.path.join(parent_dir, "cluster")
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
        if not os.path.exists(descriptions_path):
            os.makedirs(descriptions_path)

        with open(inventory_path, 'r') as file:
            inventory = yaml.safe_load(file)

        for cluster_name in inventory['all']['children']:
            try:
                print(f"Processing cluster: {cluster_name}")
                create_cluster_yaml(inventory_path, cluster_name, descriptions_path)
            except ValueError as e:
                print(f"Skipping cluster '{cluster_name}': {e}")

    # ConfigMap
    client_karmada.create_configmap_from_file(descriptions_path, "mlsysops-framework", "cluster-system-description")

    # DaemonSet YAML
    daemonset_path = files(deployment).joinpath("cluster-agents-daemonset.yaml")
    for r in parse_yaml_from_file(daemonset_path, {"KARMADA_HOST_IP": os.getenv("KARMADA_HOST_IP")}):
        client_karmada.create_or_update(r)

def deploy_node_agents(path, inventory_path):
    print("🧱 Deploying Node Agents...")
    _check_required_env_vars("KARMADA_HOST_IP", "KARMADA_API_KUBECONFIG")
    client_karmada = KubernetesLibrary("apps", "v1", os.getenv("KARMADA_API_KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"))

    descriptions_path = os.getenv("NODE_SYSTEM_DESCRIPTIONS_PATH","descriptions")
    if path:
      descriptions_path = path

    if inventory_path:
        # build the system descriptions
        parent_dir = "descriptions"
        descriptions_path = os.path.join(parent_dir,"nodes")
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
        if not os.path.exists(descriptions_path):
            os.makedirs(descriptions_path)

        with open(inventory_path, 'r') as file:
            inventory = yaml.safe_load(file)

        for cluster_name in inventory['all']['children']:
            try:
                print(f"Processing cluster: {cluster_name}")
                create_worker_node_yaml(inventory_path, cluster_name,descriptions_path)
            except ValueError as e:
                print(f"Skipping cluster '{cluster_name}': {e}")

    # ConfigMap
    print(f"Using node systems decriptions from {descriptions_path}")
    client_karmada.create_configmap_from_file(descriptions_path, "mlsysops-framework", "node-system-descriptions")

    # DaemonSet YAML
    daemonset_path = files(deployment).joinpath("node-agents-daemonset.yaml")
    for r in parse_yaml_from_file(daemonset_path, {"KARMADA_HOST_IP": os.getenv("KARMADA_HOST_IP")}):
        client_karmada.create_or_update(r)

def _apply_namespace_and_rbac(client_instance):
    # Carga de namespace.yaml
    ns_path = files(deployment).joinpath("namespace.yaml")
    for r in parse_yaml_from_file(ns_path):
        client_instance.create_or_update(r)

    # Carga de mlsysops-rbac.yaml
    rbac_path = files(deployment).joinpath("mlsysops-rbac.yaml")
    for r in parse_yaml_from_file(rbac_path):
        client_instance.create_or_update(r)
    ## Node agents deployment
    karmada_api_client.create_configmap_from_file("descriptions/nodes", "mlsysops-framework", "node-system-descriptions")
    node_agents_resources = karmada_api_client.parse_yaml("node-agents-daemonset.yaml",
                                                           {"KARMADA_HOST_IP": os.getenv("KARMADA_HOST_IP")})
    for resource in node_agents_resources:
        karmada_api_client.create_or_update(resource)

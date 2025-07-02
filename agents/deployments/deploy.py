from pathlib import Path

import kubernetes.client.rest
from jinja2 import Environment, FileSystemLoader
from kubernetes import client, config
from kubernetes.client import ApiException
from ruamel.yaml import YAML
import os
from jinja2 import Template
import subprocess


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


    def __init__(self,group=None, version=None, kubeconfig=None):

        # Load Kubernetes configuration for the default environment
        if kubeconfig:
            print(f"load conf {kubeconfig}")
            config.load_kube_config(kubeconfig)
        elif 'KUBERNETES_PORT' in os.environ:
            config.load_incluster_config()
        else:
            config.load_kube_config()

        print(f"load conf {config}")
        self.group = group
        self.version = version
        self.custom_objects_api = client.CustomObjectsApi()
        self.core_v1_api = client.CoreV1Api()
        self.apps_v1_api = client.AppsV1Api()

    def parse_yaml(self,resource_file: str = None, template_variables: dict = {}) -> list | None:
        """
        Parses a YAML file using Jinja2 templates to dynamically substitute values,
        then manages and sorts multiple resource definitions.

        Parameters:
        resource_file: str, optional
            The path to the YAML file containing resource definitions. Defaults to None.
        karmada_host_ip: str, optional
            The IP of the Karmada host to be substituted in the template. Defaults to the
            environment variable "KARMADA_HOST_IP" if not provided.

        Returns:
        list | None
            Returns a sorted list of resource definitions if the file is successfully
            parsed and contains resources. Returns None if no resources are found or if
            no file is specified.
        """
        yaml = YAML(typ='safe')  # Safe loading of YAML

        if resource_file is None:
            print("No resource file specified.")
            return None

        # Load the file and use Jinja2 for template rendering
        with open(resource_file, "r") as file:
            raw_template = file.read()

        # Render the Jinja2 template with karmada_host_ip
        template = Template(raw_template)
        rendered_template = template.render(**template_variables)

        # Parse the rendered YAML
        resources = list(yaml.load_all(rendered_template))  # Load all YAML resource definitions

        if not resources:
            print(f"No resources found in file: {resource_file}")
            return None

        # Define the order for sorting resources by 'kind'
        resource_order = ["namespace", "serviceaccount", "clusterrole", "rolebinding", "clusterrolebinding",
                          "configmap", "secret", "persistentvolumeclaim", "service", "deployment", "daemonset"]

        # Sort the resources based on the resource_order
        sorted_resources = sorted(
            resources,
            key=lambda r: resource_order.index(r["kind"].lower())
            if r["kind"].lower() in resource_order else len(resource_order)
        )

        # Process all resources (if needed, you can expand this part with further logic)
        for resource in sorted_resources:
            if not resource:
                continue  # Skip empty resources

        return sorted_resources

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


    def create_or_update(self,resource_yaml):

        try:

            kind = resource["kind"].lower()
            name = resource["metadata"].get("name","None")
            namespace = resource["metadata"].get("namespace")
            print(f"Creating/Updating resource: {name} of kind {kind} in namespace {namespace} ")
            if namespace is not None :
                existing_resource = get_method(kind, "read")(name,namespace=namespace)
                get_method(kind, "replace")(name=name, namespace=namespace, body=resource_yaml)

            else:
                existing_resource = get_method(kind, "read")(name)
                get_method(kind, "replace")(name=name,body=resource_yaml)

                print(f"Updated resource: {name}")
        except KeyError as e:
            print(f"Error parsing resource: {e}")
            return
        except client.exceptions.ApiException as e:
            if e.status == 404:
                print(f"Resource '{name}' of kind '{kind}' not found. Creating it now. {namespace}")
                if namespace is not None:
                    if kind in ['serviceaccount','configmap','daemonset',"deployment", "service", "persistentvolumeclaim"]:
                        get_method(kind, "create")(namespace=namespace, body=resource_yaml)

                    else:
                        get_method(kind, "create")(name=name, namespace=namespace, body=resource_yaml)
                else:
                    get_method(kind, "create")(body=resource_yaml)
            else:
                print(f"Error updating Service '{name}' in namespace '{namespace}': {e}")

    def create_configmap_from_file(self, descriptions_directory, namespace, name,suffixes=["*.yml", "*.yaml"]):

        directory = Path(descriptions_directory)
        if not directory.exists() or not directory.is_dir():
            print(f"Invalid directory: {descriptions_directory}")
            exit()

        # Iterate through files in the directory and filter YAML files
        file_paths = []
        for suffix in suffixes:
            file_paths += list( directory.glob(suffix) )

        files_data_object = {}
        for single_file in file_paths:
            print(f"Reading file: {single_file}")
            with open(single_file, "r") as file:
                file_data = file.read()
                files_data_object[single_file.name] = file_data

        # Create the ConfigMap body
        config_map = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=name, namespace=namespace),
            data=files_data_object
        )
        try:
            self.core_v1_api.create_namespaced_config_map(namespace, config_map)
            print(f"Created configmap {name}")
        except ApiException as e:
            if e.status != 409:
                self.core_v1_api.replace_namespaced_config_map(name, namespace, config_map)
                print(f"Updated configmap {name}")


    def delete(self, kind, namespace, name):
        try:
            get_method(kind,"delete")(name=name, namespace=namespace)
        except client.exceptions.ApiException as e:
            if e.status != 404:
                print(f"Error deleting Service: {e}")

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

    def apply_karmada_policy(self, policy_name: str, policy_body: dict, plural: str, namespaced: bool = False, namespace: str = None):
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

            env = Environment(loader=FileSystemLoader(searchpath="./"))  # Load from "templates" dir

            # Apply Cluster-Wide PropagationPolicy
            try:
                name = "mlsysops-cluster-propagation-policy"
                cluster_template = env.get_template("cluster-propagation-policy.yaml")
                rendered_cluster_policy = cluster_template.render(name=name, cluster_names=cluster_names)

                # Parse YAML to Python dictionary
                yaml = YAML(typ='safe')
                cluster_policy_body = yaml.load(rendered_cluster_policy)

                # Apply the Cluster-Wide PropagationPolicy
                self.apply_karmada_policy(
                    policy_name=name,
                    policy_body=cluster_policy_body,
                    plural="clusterpropagationpolicies",
                    namespaced=False,
                )

            except Exception as e:
                print(f"Error applying Cluster-Wide PropagationPolicy: {e}")

            # Apply Simple PropagationPolicy
            try:
                name = "mlsysops-propagate-policy"
                simple_template = env.get_template("propagation-policy.yaml")
                rendered_simple_policy = simple_template.render(name=name, cluster_names=cluster_names)

                # Parse YAML to Python dictionary
                yaml = YAML(typ='safe')
                simple_policy_body = yaml.load(rendered_simple_policy)

                # Apply the Simple PropagationPolicy
                self.apply_karmada_policy(
                    policy_name=name,
                    policy_body=simple_policy_body,
                    plural="propagationpolicies",
                    namespaced=True,
                    namespace="default"
                )

            except Exception as e:
                print(f"Error applying Simple PropagationPolicy: {e}")

        except Exception as e:
            print(f"Error applying PropagationPolicies: {e}")

if __name__ == "__main__":

    # Create Karmada objects - load the client with the Karmada host kubeconfig
    kubernetes_client = KubernetesLibrary("apps", "v1", os.getenv("KARMADA_HOST_KUBECONFIG","/etc/rancher/k3s/k3s.yaml"))
    #
    # Create or update the namespace, RBAC, and service account for the MLSAgent
    namespace_resources = kubernetes_client.parse_yaml("namespace.yaml")
    for resource in namespace_resources:
        kubernetes_client.create_or_update(resource)
    #
    rbac_resources = kubernetes_client.parse_yaml("mlsysops-rbac.yaml")
    for resource in rbac_resources:
        kubernetes_client.create_or_update(resource)

    # Load xmpp
    xmpp_resources = kubernetes_client.parse_yaml("xmpp/deployment.yaml",
                                                    {"POD_IP": os.getenv("KARMADA_HOST_IP")})
    for resource in xmpp_resources:
        kubernetes_client.create_or_update(resource)

    nb_api_resource = kubernetes_client.parse_yaml("api-service-deployment.yaml",
                                                   {"KARMADA_HOST_IP": os.getenv("KARMADA_HOST_IP")})
    for resource in nb_api_resource:
        kubernetes_client.create_or_update(resource)

    for resource in kubernetes_client.parse_yaml("redis-stack-deployment.yaml",{"KARMADA_HOST_IP": os.getenv("KARMADA_HOST_IP")}):
        kubernetes_client.create_or_update(resource)

    # Load continuum agent configmaps
    kubernetes_client.create_configmap_from_file("descriptions/continuum",
                                                 "mlsysops-framework",
                                                 "continuum-system-description")
    kubernetes_client.create_configmap_from_file("descriptions/continuum",
                                                 "mlsysops-framework",
                                                 "continuum-karmadapi-config",
                                                 suffixes=["*.kubeconfig"])

    continuum_agent_resource = kubernetes_client.parse_yaml("continuum-agent-daemonset.yaml")
    for resource in continuum_agent_resource:
        kubernetes_client.create_or_update(resource)


    ## Cluster agent deployment
    karmada_api_client = KubernetesLibrary("apps", "v1", os.getenv("KARMADA_API_KUBECONFIG","/etc/rancher/k3s/k3s.yaml"))


    # add policies
    karmada_api_client.apply_mlsysops_propagation_policies()

    namespace_resources = karmada_api_client.parse_yaml("namespace.yaml")
    for resource in namespace_resources:
        karmada_api_client.create_or_update(resource)
    #
    rbac_resources = karmada_api_client.parse_yaml("mlsysops-rbac.yaml")
    for resource in rbac_resources:
        karmada_api_client.create_or_update(resource)

    karmada_api_client.create_configmap_from_file("descriptions/clusters",
                                                     "mlsysops-framework",
                                                   "cluster-system-description")

    cluster_agents_resources = karmada_api_client.parse_yaml("cluster-agents-daemonset.yaml",
                                                              {"KARMADA_HOST_IP": os.getenv("KARMADA_HOST_IP")})
    for resource in cluster_agents_resources:
        karmada_api_client.create_or_update(resource)

    ## Node agents deployment
    karmada_api_client.create_configmap_from_file("descriptions/nodes", "mlsysops-framework", "node-system-descriptions")
    node_agents_resources = karmada_api_client.parse_yaml("node-agents-daemonset.yaml",
                                                           {"KARMADA_HOST_IP": os.getenv("KARMADA_HOST_IP")})
    for resource in node_agents_resources:
        karmada_api_client.create_or_update(resource)

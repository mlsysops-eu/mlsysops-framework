import os, click
from ..utils.ui import ok, warn, err
from mlsysops_cli.deployment.deploy import KubernetesLibrary

@click.group(help="Agent management commands (policies & configs)")
def agent():
    """Manage policies and configs for agents."""
    pass

policies_configmap = {
    "cluster": "cluster-agents-policies",
    "continuum": "continuum-policies",
    "node": "node-agents-policies"
}

@agent.command(name="set-policy", help="Add/update a policy for an agent (short: sp)")
@click.option('--agent', type=click.Choice(['cluster', 'continuum', 'node']), required=True)
@click.option('--file', 'policy_file', type=click.Path(exists=True), required=True)
def policy_add_or_update(agent, policy_file):
    configmap_name = policies_configmap[agent]
    namespace = "mlsysops-framework"
    try:
        with open(policy_file, 'r', encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        err(f"Error reading file '{policy_file}': {e}"); return
    client_k8s = KubernetesLibrary("apps", "v1",
                                   os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
                                   context="karmada-apiserver")
    try:
        key = os.path.basename(policy_file)
        client_k8s.update_configmap_data(namespace, configmap_name, key, content)
        ok(f"Policy added to {agent} agent configmap '{configmap_name}'.")
    except Exception as e:
        err(f"Failed to update ConfigMap: {e}")

agent.add_command(policy_add_or_update, name="sp")  # short alias

@agent.command("delete-policy", help="Delete a policy by name from an agent (short: dp)")
@click.option("--agent", type=click.Choice(["cluster", "continuum", "node"]), required=True)
@click.argument("name", type=str)
def policy_delete(agent: str, name: str):
    configmap_name = policies_configmap[agent]
    namespace = "mlsysops-framework"
    client_k8s = KubernetesLibrary("apps", "v1",
                                   os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
                                   context="karmada-apiserver")
    try:
        cm = client_k8s.core_v1_api.read_namespaced_config_map(configmap_name, namespace)
        if not cm.data or name not in cm.data:
            warn(f"Policy '{name}' not found in '{configmap_name}'."); return
        del cm.data[name]
        client_k8s.core_v1_api.replace_namespaced_config_map(configmap_name, namespace, cm)
        client_k8s.annotate_pod()
        ok(f"Policy '{name}' deleted from {agent} agent policies.")
    except Exception as e:
        err(f"Failed to delete policy: {e}")

agent.add_command(policy_delete, name="dp")  # short alias

configmap_map = {
    "cluster": "cluster-agents-config",
    "continuum": "continuum-agent-config",
    "node": "node-agents-config",
}

@agent.command("set-config", help="Add or update a config entry for an agent (short: sc)")
@click.option("--agent", type=click.Choice(["cluster", "continuum", "node"]), required=True)
@click.option("--file", "config_file", type=click.Path(exists=True), required=True)
def set_config(agent: str, config_file: str):
    configmap_name = configmap_map[agent]
    namespace = "mlsysops-framework"
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        err(f"Error reading file '{config_file}': {e}"); return
    client_k8s = KubernetesLibrary("apps", "v1",
                                   os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
                                   context="karmada-apiserver")
    try:
        key = os.path.basename(config_file)
        client_k8s.update_configmap_data(namespace, configmap_name, key, content)
        ok(f"Config '{key}' added/updated in {agent} agent configmap '{configmap_name}'.")
    except Exception as e:
        err(f"Failed to update ConfigMap: {e}")

agent.add_command(set_config, name="sc")  # short alias

@agent.command("delete-config", help="Delete a config key from an agent (short: dc)")
@click.option("--agent", type=click.Choice(["cluster", "continuum", "node"]), required=True)
@click.argument("key", type=str)
def delete_config(agent: str, key: str):
    configmap_name = configmap_map[agent]
    namespace = "mlsysops-framework"
    client_k8s = KubernetesLibrary("apps", "v1",
                                   os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
                                   context="karmada-apiserver")
    try:
        cm = client_k8s.core_v1_api.read_namespaced_config_map(configmap_name, namespace)
        if not cm.data or key not in cm.data:
            warn(f"Config key '{key}' not found in '{configmap_name}'."); return
        del cm.data[key]
        client_k8s.core_v1_api.replace_namespaced_config_map(configmap_name, namespace, cm)
        ok(f"Config key '{key}' deleted from {agent} agent configmap '{configmap_name}'.")
    except Exception as e:
        err(f"Failed to delete config: {e}")

agent.add_command(delete_config, name="dc")  # short alias

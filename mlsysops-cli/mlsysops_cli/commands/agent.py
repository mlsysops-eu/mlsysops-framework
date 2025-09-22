# mlsysops_cli/commands/agent.py
import os
import json
import click
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from kubernetes.client.exceptions import ApiException

from ..utils.ui import rule, ok, warn, err, info
from ..utils.alias import AliasedGroup
from mlsysops_cli.deployment.deploy import KubernetesLibrary

# Silence the noisy TLS warning from urllib3; we print one friendly note instead.
urllib3.disable_warnings(InsecureRequestWarning)

AGENT_ALIASES = {
    "sp": "set-policy",
    "dp": "delete-policy",
    "sc": "set-config",
    "dc": "delete-config",
}

@click.group(
    cls=AliasedGroup,
    aliases=AGENT_ALIASES,
    help="Agent management commands (policies & configs)",
)
@click.option(
    "--kubeconfig", "-k",
    "kubeconfig_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
    required=True,
    help="Path to the kubeconfig that can access the Karmada API (required).",
)
@click.pass_context
def agent(ctx: click.Context, kubeconfig_path: str):
    """Manage policies and configs for agents."""
    ctx.ensure_object(dict)
    ctx.obj["kubeconfig"] = kubeconfig_path

policies_configmap = {
    "cluster": "cluster-agents-policies",
    "continuum": "continuum-policies",
    "node": "node-agents-policies",
}

configmap_map = {
    "cluster": "cluster-agents-config",
    "continuum": "continuum-agent-config",
    "node": "node-agents-config",
}

# ---------- helpers ---------------------------------------------------------

def _k8s_client(kubeconfig: str):
    """Build a KubernetesLibrary client with a single, friendly TLS note."""
    # TLS heads-up only once per process
    if os.getenv("MLSYSOPS_TLS_NOTE_SHOWN") != "1":
        warn("Connecting to Kubernetes with TLS verification disabled. "
             "For production, provide a valid cluster CA in your kubeconfig.")
        os.environ["MLSYSOPS_TLS_NOTE_SHOWN"] = "1"

    return KubernetesLibrary("apps", "v1", kubeconfig, context="karmada-apiserver")

def _parse_api_error(e: ApiException) -> dict:
    code = getattr(e, "status", None) or 0
    reason = getattr(e, "reason", "") or "Error"
    message = None
    try:
        body = e.body if isinstance(e.body, str) else ""
        if body:
            j = json.loads(body)
            message = j.get("message") or j.get("status") or body
    except Exception:
        message = str(e)
    audit_id = None
    try:
        if hasattr(e, "headers") and e.headers:
            audit_id = e.headers.get("Audit-Id")
    except Exception:
        pass
    return {"code": code, "reason": reason, "message": message, "audit_id": audit_id}

def _nice_k8s_error(action: str, e: ApiException, *, resource: str, namespace: str):
    info = _parse_api_error(e)
    hdr = f"{info['code']} {info['reason']}".strip()
    err(f"{action} failed: {hdr}")
    if info["message"]:
        warn(f"↳ {info['message']}")
    warn(f"resource: {resource}  namespace: {namespace}")

    code = info["code"]
    if code == 401:
        click.echo("• Authentication failed. Check the credentials in your kubeconfig/context.")
        click.echo("  - kubectl config current-context --kubeconfig \"$KUBECONFIG_PATH\"")
    elif code == 403:
        click.echo("• Permission denied (RBAC). Verify access:")
        click.echo(f"  - kubectl auth can-i update configmaps -n {namespace} --kubeconfig \"$KUBECONFIG_PATH\"")
    elif code == 404:
        click.echo("• Not found. Check names/namespace/context:")
        click.echo(f"  - kubectl -n {namespace} get configmap --kubeconfig \"$KUBECONFIG_PATH\"")
    else:
        click.echo("• Check cluster reachability and credentials.")

    if info["audit_id"]:
        click.echo(f"• Kubernetes Audit ID: {info['audit_id']}")
    raise SystemExit(3)

# ---------- commands --------------------------------------------------------

@agent.command(name="set-policy", help="Add or update a policy file for an agent (short: sp)")
@click.option('--agent', type=click.Choice(['cluster', 'continuum', 'node']), required=True, help="Agent type")
@click.option('--file', 'policy_file', type=click.Path(exists=True), required=True, help="Path to the policy file")
@click.pass_context
def policy_add_or_update(ctx: click.Context, agent: str, policy_file: str):
    namespace = "mlsysops-framework"
    configmap_name = policies_configmap[agent]
    rule(f"📜 Set policy → {agent}", "cyan")
    info(f"Using kubeconfig: {ctx.obj['kubeconfig']}")

    try:
        with open(policy_file, 'r', encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        err(f"Couldn't read file '{policy_file}': {e}")
        raise SystemExit(2)

    client_k8s = _k8s_client(ctx.obj["kubeconfig"])

    try:
        key = os.path.basename(policy_file)
        client_k8s.update_configmap_data(namespace, configmap_name, key, content)
        ok(f"Policy '{key}' added/updated in {agent} configmap '{configmap_name}'.")
    except ApiException as e:
        _nice_k8s_error("Update ConfigMap", e, resource=f"configmap/{configmap_name}", namespace=namespace)
    except Exception as e:
        err(f"Failed to update ConfigMap: {e}")
        raise SystemExit(3)

@agent.command(name="delete-policy", help="Delete a policy by name from an agent (short: dp)")
@click.option("--agent", type=click.Choice(["cluster", "continuum", "node"]), required=True, help="Agent type")
@click.argument("name", type=str)
@click.pass_context
def policy_delete(ctx: click.Context, agent: str, name: str):
    namespace = "mlsysops-framework"
    configmap_name = policies_configmap[agent]
    rule(f"🗑️  Delete policy → {agent}", "yellow")
    info(f"Using kubeconfig: {ctx.obj['kubeconfig']}")

    client_k8s = _k8s_client(ctx.obj["kubeconfig"])

    try:
        cm = client_k8s.core_v1_api.read_namespaced_config_map(configmap_name, namespace)
        if not cm.data or name not in cm.data:
            warn(f"Policy '{name}' not found in '{configmap_name}'.")
            raise SystemExit(2)
        del cm.data[name]
        client_k8s.core_v1_api.replace_namespaced_config_map(configmap_name, namespace, cm)
        try:
            client_k8s.annotate_pod()
        except Exception:
            pass
        ok(f"Policy '{name}' deleted from {agent} policies.")
    except ApiException as e:
        _nice_k8s_error("Delete policy", e, resource=f"configmap/{configmap_name}", namespace=namespace)
    except Exception as e:
        err(f"Failed to delete policy: {e}")
        raise SystemExit(3)

@agent.command(name="set-config", help="Add or update a config entry for an agent (short: sc)")
@click.option("--agent", type=click.Choice(["cluster", "continuum", "node"]), required=True, help="Agent type")
@click.option("--file", "config_file", type=click.Path(exists=True), required=True, help="Path to the config file")
@click.pass_context
def set_config(ctx: click.Context, agent: str, config_file: str):
    namespace = "mlsysops-framework"
    configmap_name = configmap_map[agent]
    rule(f"⚙️  Set config → {agent}", "cyan")
    info(f"Using kubeconfig: {ctx.obj['kubeconfig']}")

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        err(f"Couldn't read file '{config_file}': {e}")
        raise SystemExit(2)

    client_k8s = _k8s_client(ctx.obj["kubeconfig"])

    try:
        key = os.path.basename(config_file)
        client_k8s.update_configmap_data(namespace, configmap_name, key, content)
        ok(f"Config '{key}' added/updated in {agent} configmap '{configmap_name}'.")
    except ApiException as e:
        _nice_k8s_error("Update ConfigMap", e, resource=f"configmap/{configmap_name}", namespace=namespace)
    except Exception as e:
        err(f"Failed to update ConfigMap: {e}")
        raise SystemExit(3)

@agent.command(name="delete-config", help="Delete a config key from an agent (short: dc)")
@click.option("--agent", type=click.Choice(["cluster", "continuum", "node"]), required=True, help="Agent type")
@click.argument("key", type=str)
@click.pass_context
def delete_config(ctx: click.Context, agent: str, key: str):
    namespace = "mlsysops-framework"
    configmap_name = configmap_map[agent]
    rule(f"🗑️  Delete config → {agent}", "yellow")
    info(f"Using kubeconfig: {ctx.obj['kubeconfig']}")

    client_k8s = _k8s_client(ctx.obj["kubeconfig"])

    try:
        cm = client_k8s.core_v1_api.read_namespaced_config_map(configmap_name, namespace)
        if not cm.data or key not in cm.data:
            warn(f"Config key '{key}' not found in '{configmap_name}'.")
            raise SystemExit(2)
        del cm.data[key]
        client_k8s.core_v1_api.replace_namespaced_config_map(configmap_name, namespace, cm)
        ok(f"Config key '{key}' deleted from {agent} config '{configmap_name}'.")
    except ApiException as e:
        _nice_k8s_error("Delete config key", e, resource=f"configmap/{configmap_name}", namespace=namespace)
    except Exception as e:
        err(f"Failed to delete config: {e}")
        raise SystemExit(3)

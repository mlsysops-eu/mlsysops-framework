import click
import requests
from typing import Optional

from mlsysops_cli.config import BASE
from mlsysops_cli.utils.ui import rule, info, ok, warn, err, table_kv
from mlsysops_cli.utils.alias import AliasedGroup

# Runtime deployment helpers from your project
from mlsysops_cli.deployment.deploy import (
    run_deploy_all,
    deploy_core_services,
    deploy_continuum_agents,
    deploy_cluster_agents,
    deploy_node_agents,
)
from mlsysops_cli.deployment.descriptions_util import create_app_yaml

# Hidden aliases (won't show in --help)
INFRA_ALIASES = {
    "ls": "list",
    "da": "deploy-all",
    "ds": "deploy-services",
    "dco": "deploy-continuum",
    "dcl": "deploy-cluster",
    "dn": "deploy-node",
    "cta": "create-test-app-description",
}

@click.group(cls=AliasedGroup, aliases=INFRA_ALIASES,
             help="Infrastructure and framework deployment commands")
def infra():
    pass


# ---- list (HTTP to your API)
@infra.command(name="list", help="Get infrastructure status (short: ls)")
@click.option('--type', 'itype', type=click.Choice(['Continuum', 'Cluster', 'Datacenter', 'All'], case_sensitive=False),
              required=True)
@click.option('--name', type=str, default=None)
def list_infra(itype: str, name: Optional[str]):
    api_url = f"{BASE}/infra/list/"
    params = {'type': itype}
    if name:
        params['name'] = name

    rule("🏗️ Infrastructure Status", "magenta")
    try:
        resp = requests.get(api_url, headers={'Content-Type': 'application/json'}, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                rows = [(i.get("name", "N/A"), i.get("type", "N/A")) for i in data["items"]]
                table_kv(rows or [("info", "No items")], title="Infra Items")
            else:
                table_kv(list(data.items()), title="Raw Response") if isinstance(data, dict) else click.echo(resp.text)
        else:
            try:
                detail = resp.json().get("detail", "Unknown error")
            except Exception:
                detail = resp.text
            err(f"Failed to retrieve data. HTTP {resp.status_code} :: {detail}")
    except requests.exceptions.RequestException as e:
        err(f"Connection Error: {e}")


# ---- pipeline commands (your Python functions)
@infra.command(name="deploy-all", help="Deploy all components: core, continuum, clusters, nodes (short: da)")
@click.option('--path', type=click.Path(exists=True), required=False,
              help='Path to descriptions dir (must include continuum/cluster/node subdirs)')
@click.option('--inventory', type=click.Path(exists=True), required=False,
              help='Path to the inventory YAML used by Karmada setup.')
def deploy_all_cmd(path, inventory):
    if path and inventory:
        err('Provide only --path or --inventory.'); return
    rule("🚀 Full Framework Deployment", "cyan")
    try:
        run_deploy_all(path, inventory)
        ok("Framework deployment finished.")
    except Exception as e:
        err(f"Error during full deployment: {e}")


@infra.command(name="deploy-services", help="Deploy core services: ejabberd, Redis, API (short: ds)")
def deploy_services_cmd():
    rule("🏛️ Core Services", "cyan")
    try:
        deploy_core_services()
        ok("Core services deployed.")
    except Exception as e:
        err(f"Error during core services deployment: {e}")


@infra.command(name="deploy-continuum", help="Deploy the continuum agent (short: dco)")
@click.option('--path', type=click.Path(exists=True), required=False)
@click.option('--inventory', type=click.Path(exists=True), required=False)
def deploy_continuum_cmd(path, inventory):
    if path and inventory:
        err('Provide only --path or --inventory.'); return
    try:
        deploy_continuum_agents(path, inventory)
        ok("Continuum agent deployed.")
    except Exception as e:
        err(f"Error during continuum agent deployment: {e}")


@infra.command(name="deploy-cluster", help="Deploy the cluster agents (short: dcl)")
@click.option('--path', type=click.Path(exists=True), required=False)
@click.option('--inventory', type=click.Path(exists=True), required=False)
def deploy_cluster_cmd(path, inventory):
    if path and inventory:
        err('Provide only --path or --inventory.'); return
    try:
        deploy_cluster_agents(path, inventory)
        ok("Cluster agents deployed.")
    except Exception as e:
        err(f"Error during cluster agents deployment: {e}")


@infra.command(name="deploy-node", help="Deploy the node agents (short: dn)")
@click.option('--path', type=click.Path(exists=True), required=False)
@click.option('--inventory', type=click.Path(exists=True), required=False)
def deploy_node_cmd(path, inventory):
    if path and inventory:
        err('Provide only --path or --inventory.'); return
    try:
        deploy_node_agents(path, inventory)
        ok("Node agents deployed.")
    except Exception as e:
        err(f"Error during node agents deployment: {e}")


@infra.command(name="create-test-app-description",
               help="Create a test app description from an inventory file (short: cta)")
@click.option('--inventory', type=click.Path(exists=True), required=True,
              help='Path to the inventory YAML used by Karmada setup.')
@click.option('--cluster', type=str, required=False, help='Specific cluster name (optional)')
def create_test_app_description_cmd(inventory, cluster):
    try:
        create_app_yaml(inventory, cluster)
        ok("Test application description created.")
    except Exception as e:
        err(f"Error creating test application description: {e}")

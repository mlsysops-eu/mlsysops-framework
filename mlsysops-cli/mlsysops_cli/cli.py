#!/usr/bin/env python3
import asyncio
import sys
import traceback

import click
import requests
import yaml
import json
import os
from mlsysops_cli.deployment.deploy import (
    run_deploy_all,
    deploy_core_services,
    deploy_continuum_agents,
    deploy_cluster_agents,
    deploy_node_agents,
)

from mlsysops_cli.deployment.descriptions_util import create_app_yaml
from mlsysops_cli.deployment.deploy import KubernetesLibrary

# Configurable IP and PORT via environment variables
IP = os.getenv("MLS_API_IP", "127.0.0.1")
PORT = os.getenv("MLS_API_PORT", "8000")


@click.group(help="Command-line interface for managing MLSysOps apps, infra, ML models, and agents.")
def cli():
    pass


# -----------------------------------------------------------------------------
# Application commands
# -----------------------------------------------------------------------------
@click.group(help="Commands related to applications")
def apps():
    pass


@click.command(help='Deploy an application based on a YAML file (local or URI). Returns an app ID.')
@click.option('--path', type=click.Path(exists=True), required=False, help='Path to the application YAML file')
@click.option('--uri', type=str, required=False, help='URI to get the YAML description from')
def deploy_app(path, uri):
    api_endpoint = f"http://{IP}:{PORT}/apps/deploy"

    if path and uri:
        click.echo('Error: Provide only --path or --uri.')
        return
    if not (path or uri):
        click.echo('Error: You must provide --path or --uri.')
        return

    try:
        yaml_data = yaml.safe_load(open(path)) if path else yaml.safe_load(requests.get(uri).text)
        json_data = json.dumps(yaml_data)
        headers = {'Content-Type': 'application/json'}
        response = requests.post(api_endpoint, headers=headers, data=json_data)

        if response.status_code == 200:
            click.secho("DESCRIPTION UPLOADED SUCCESSFULLY!", fg='green')
            print(response.text)
        else:
            click.secho(f"ERROR: {response.json().get('detail', 'Unknown error')}", fg='red')
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg='red')


@click.command(help='Returns the system applications status')
def list_all():
    api_url = f"http://{IP}:{PORT}/apps/list_all/"
    try:
        response = requests.get(api_url, headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            system_status = response.json().get("System_status", {})
            if not system_status:
                click.secho("No applications found.", fg='yellow')
                return
            click.secho(f"{'Application':<20} {'Status':<15}", fg='bright_blue')
            click.secho(f"{'-' * 20} {'-' * 15}", fg='bright_blue')
            for app_id, status in system_status.items():
                click.echo(f"{app_id:<20} {status:<15}")
        else:
            click.secho(f"Error: {response.json().get('detail', 'Unknown error')}", fg='red')
    except Exception as e:
        click.secho(f"Connection Error: {e}", fg='red')


@click.command(help='Takes as Input a ticket and returns the performance of the app')
@click.argument('app_id')
def get_app_performance(app_id):
    """Get the performance details of a specific app based on the app_id."""
    api_url = f"http://{IP}:{PORT}/apps/performance/{app_id}"
    response = requests.get(api_url, headers={'Content-Type': 'application/json'})

    if response.status_code == 200:
        try:
            responses = response.json()

            # Print Header
            click.echo(click.style(f"\nApplication Performance Metrics of {app_id}:", fg="cyan", bold=True))
            separator = "-" * 40
            click.secho(separator, fg="bright_blue")
            click.secho(f"{'Metric Name':<25} | {'Value':<10}", fg="bright_blue", bold=True)
            click.secho(separator, fg="bright_blue")

            # Extract and print metrics
            for metric in responses:
                if isinstance(metric, list) and len(metric) == 2:
                    metric_name = metric[0]
                    metric_data = metric[1]  # This could be None

                    # Safely extract 'value', handling None cases
                    if isinstance(metric_data, dict):
                        metric_value = metric_data.get('value', 'N/A')
                    else:
                        metric_value = "No Data"  # Handling case where metric_data is None

                    click.echo(f"{metric_name:<25} | {metric_value:<10}")

            click.secho(separator, fg="bright_blue")

        except ValueError:
            click.echo(click.style("❌ ERROR: Failed to parse JSON response", fg='red'))

    else:
        try:
            error_message = response.json().get("detail", "Unknown error")
        except ValueError:
            error_message = "Unknown error (Failed to parse error response)"

        click.echo(click.style(f"❌ ERROR. Reason: {error_message}", fg='red'))


@click.command(help='Takes as Input a ticket and returns the deployment status')
@click.argument('app_id')
def get_app_status(app_id):
    """Get the status of a specific app based on the app_id."""
    api_url = f"http://{IP}:{PORT}/apps/status/{app_id}"
    response = requests.get(api_url, headers={'Content-Type': 'application/json'})

    if response.status_code == 200:
        try:
            responses = response.json()
        except ValueError:
            responses = json.loads(response.text)

        app_id = responses.get('app_id', 'Unknown')
        status = responses.get('status', 'Unknown')
        click.echo(click.style(f"{'AppId':<20} {'Status':<15}", fg='bright_blue'))
        click.echo(click.style(f"{'-' * 15} {'-' * 15}", fg='bright_blue'))
        click.echo(click.style(f"{app_id:<15} {status:<15}", fg='bright_green'))

    else:
        error_message = response.json().get("detail", "Unknown error")
        click.echo(click.style(f"ERROR. Reason: {error_message}", fg='red'))


# ----------------------------------------------------------------------------
# Get Application Details Command (based on app ID)
# ----------------------------------------------------------------------------
@click.command(help='Takes as Input a ticket and returns the deployment status')
@click.argument('app_id')
def get_app_details(app_id):
    """Get the status of a specific app based on the app_id."""
    api_url = f"http://{IP}:{PORT}/apps/apps/details/{app_id}"
    response = requests.get(api_url, headers={'Content-Type': 'application/json'})

    if response.status_code == 200:
        try:
            responses = response.json()
        except ValueError:
            responses = json.loads(response.text)

        # Print Application ID and State
        click.secho(f"\nApplication ID: {responses['app_id']}", fg="cyan", bold=True)
        click.secho(f"State: {responses['state']}", fg="green", bold=True)
        click.echo("\nDeployment Details:")

        # Table Header
        header = f"{'Component':<20} | {'Pod Name':<25} | {'Status':<12} | {'Location (Node / Cluster)':<30}"
        separator = "-" * len(header)

        click.secho(separator, fg="bright_blue")
        click.secho(header, fg="bright_blue", bold=True)
        click.secho(separator, fg="bright_blue")

        # Print Component Details
        for component in responses['components']:
            component_name = component['name']
            pods = component['details']['pods']

            if isinstance(pods, list):
                for pod in pods:
                    status_color = "green" if pod['pod_status'].lower() == "running" else "red"
                    pod_status = click.style(pod['pod_status'], fg=status_color, bold=True)
                    node_info = f"{pod['node_name']} / {pod['cluster_name']}"

                    click.echo(f"{component_name:<20} | {pod['pod_name']:<25} | {pod_status:<12} | {node_info:<30}")

            else:
                click.echo(f"{component_name:<20} | {'N/A':<25} | {click.style('N/A', fg='red'):<12} | {'N/A':<30}")

        click.secho(separator, fg="bright_blue")

    else:
        error_message = response.json().get("detail", "Unknown error")
        click.echo(click.style(f"ERROR. Reason: {error_message}", fg='red', bold=True))


@click.command(help='Takes as Input a ticket, cancels the deployment (if any) and invalidates the ticket')
@click.argument('app_id')
def remove_app(app_id):
    """GetApplicationStatus Task 3 functionality goes here."""
    click.echo(f'Remove the application description of : {app_id} ')
    api_url = f"http://{IP}:{PORT}/apps/remove/{app_id}"

    response = requests.delete(api_url,
                               data=json.dumps({'app_id': app_id}),
                               headers={'Content-Type': 'application/json'}
                               )
    print(response.json())
    if response.status_code == 200:
        responses = response.json()
        click.echo(click.style(f"AppID:{responses['app_id']}  status updated to 'To_be_removed'.", fg='bright_blue'))

    else:
        error_message = response.json().get("detail", "Unknown error")
        click.echo(click.style(f"ERROR. Reason: {error_message}", fg='red'))


apps.add_command(deploy_app)
apps.add_command(list_all)
apps.add_command(get_app_status)
apps.add_command(get_app_details)
apps.add_command(get_app_performance)
apps.add_command(remove_app)

cli.add_command(apps)


# -----------------------------------------------------------------------------
# Infrastructure commands
# -----------------------------------------------------------------------------
@click.group(help="Commands related to infrastructure")
def infra():
    pass


@click.command(help="Get infrastructure status")
@click.option('--type', type=click.Choice(['Continuum', 'Cluster', 'Datacenter', 'All'], case_sensitive=False),
              required=True)
@click.option('--name', type=str, default=None)
def list_infra(type, name):
    api_url = f"http://{IP}:{PORT}/infra/list/"
    params = {'type': type}
    if name:
        params['name'] = name

    try:
        response = requests.get(api_url, headers={'Content-Type': 'application/json'}, params=params)
        if response.status_code == 200:
            click.echo(response.json())
        else:
            click.secho(f"Failed to retrieve data. HTTP {response.status_code}", fg='red')
    except requests.exceptions.RequestException as e:
        click.secho(f"Connection Error: {e}", fg='red')


infra.add_command(list_infra)
cli.add_command(infra)


# -----------------------------------------------------------------------------
# ML model commands
# -----------------------------------------------------------------------------
@click.group(help="Commands related to ML models")
def ml():
    pass


@click.command(help='Deploy a ML model based on a YAML file (local or URI)')
@click.option('--path', type=click.Path(exists=True), required=False, help='Path to the ML model YAML file')
@click.option('--uri', type=str, required=False, help='URI to get the description from')
def deploy_ml(path, uri):
    api_endpoint = f"http://{IP}:{PORT}/ml/deploy_ml"

    if path and uri:
        click.secho('Error: Provide only --path or --uri.', fg='red')
        return

    try:
        if path:
            with open(path, 'rb') as file:
                files = {'file': (path, file, 'application/x-yaml')}
                response = requests.post(api_endpoint, files=files)
        else:
            response = requests.post(api_endpoint, json={'uri': uri}, headers={'Content-Type': 'application/json'})

        if response.status_code == 200:
            click.secho("ML MODEL UPLOADED SUCCESSFULLY!", fg='green')
            print(response.json())
        else:
            click.secho(f"ERROR: {response.json().get('detail', 'Unknown error')}", fg='red')
    except Exception as e:
        click.secho(f"Upload Error: {str(e)}", fg='red')


ml.add_command(deploy_ml)
cli.add_command(ml)


# -----------------------------------------------------------------------------
# Framework (agents) commands
# -----------------------------------------------------------------------------

@click.group(help="Commands to initialize the MLSysOps framework agents")
def framework():
    pass


@click.command(help="Deploy all components (core services, continuum, clusters, nodes)")
@click.option('--path', type=click.Path(exists=True), required=False,
              help='Path to the desriptions directory. It MUST include path/continuum,path/cluster,path/node')
@click.option('--inventory', type=click.Path(exists=True), required=False,
              help='Path to the inventory YAML that was used from cluster/karmada setup ansible script.')
def deploy_all(path, inventory):
    # Ensure only one of the --path or --uri options is provided
    if path and inventory:
        click.secho('❌ Error: Provide only --path or --uri.')
        return
    try:
        run_deploy_all(path, inventory)
    except Exception as e:
        click.secho(f"❌ Error during full deployment: {e}", fg='red')


@click.command(help="Deploy only core services: ejabberd, Redis, API")
def deploy_services():
    try:
        deploy_core_services()
    except Exception as e:
        click.secho(f"❌ Error during core services deployment: {e}", fg='red')


@click.command(help="Deploy the continuum agent")
@click.option('--path', type=click.Path(exists=True), required=False,
              help='Path to the desriptions directory. It MUST include path/continuum,path/cluster,path/node')
@click.option('--inventory', type=click.Path(exists=True), required=False,
              help='Path to the inventory YAML that was used from cluster/karmada setup ansible script.')
def deploy_continuum(path, inventory):
    # Ensure only one of the --path or --uri options is provided
    if path and inventory:
        click.secho('❌ Error: Provide only --path or --uri.')
        return
    try:
        deploy_continuum_agents(path, inventory)
    except Exception as e:
        click.secho(f"❌ Error during continuum agent deployment: {e}", fg='red')


@click.command(help="Deploy the cluster agents")
@click.option('--path', type=click.Path(exists=True), required=False,
              help='Path to the desriptions directory. It MUST include path/continuum,path/cluster,path/node')
@click.option('--inventory', type=click.Path(exists=True), required=False,
              help='Path to the inventory YAML that was used from cluster/karmada setup ansible script.')
def deploy_cluster(path, inventory):
    # Ensure only one of the --path or --uri options is provided
    if path and inventory:
        click.secho('❌ Error: Provide only --path or --uri.')
        return
    try:
        deploy_cluster_agents(path, inventory)
    except Exception as e:
        click.secho(f"❌ Error during cluster agents deployment: {e}", fg='red')


@click.command(help="Deploy the node agents")
@click.option('--path', type=click.Path(exists=True), required=False,
              help='Path to the desriptions directory. It MUST include path/continuum,path/cluster,path/node')
@click.option('--inventory', type=click.Path(exists=True), required=False,
              help='Path to the inventory YAML that was used from cluster/karmada setup ansible script.')
def deploy_node(path, inventory):
    # Ensure only one of the --path or --uri options is provided
    if path and inventory:
        click.secho('❌ Error: Provide only --path or --uri.')
        return

    try:
        deploy_node_agents(path, inventory)
    except Exception as e:
        click.secho(f"❌ Error during node agents deployment: {e}", fg='red')


@click.command(help="Create a test application description using an inventory YAML.")
@click.option('--inventory', type=click.Path(exists=True), required=True,
              help='Path to the inventory YAML that was used from cluster/karmada setup ansible script.')
@click.option('--cluster', type=str, required=False,
              help='Cluster name to prepare the test application description for.')
def create_test_app_description(inventory, cluster):
    try:
        create_app_yaml(inventory, cluster)
    except Exception as e:
        click.secho(f"❌ Error during test application descriptions creation: {e}", fg='red')

# -----------------------------------------------------------------------------
# Deploy FITA command
# -----------------------------------------------------------------------------

@framework.command('deploy-fita')
@click.option('--release-name', required=True, help='The name for the Helm release.')
@click.option('--chart-path', required=True, help='The path to the Helm chart directory.')
@click.option('--namespace', default='default', show_default=True, help='The Kubernetes namespace to deploy into.')
@click.option('--create-namespace', is_flag=True, help='Create the namespace if it does not exist.')
@click.option('--values', '-f', multiple=True, type=click.Path(exists=True), help='Path to a Helm values YAML file. Can be specified multiple times.')
async def deploy_fita(release_name, chart_path, namespace, create_namespace, values):
    """
    Deploys FITA components using a Helm chart with asyncio.

    This command wraps 'helm install' to provide a standardized deployment method.
    """
    click.echo(f"🚀  Starting FITA deployment for release '{release_name}'...")

    # --- Construct the Helm Command ---
    # We start with the base command.
    helm_command = [
        'helm', 'install', release_name, chart_path,
        '--namespace', namespace
    ]

    # If the --create-namespace flag is used, add it to the command.
    if create_namespace:
        helm_command.append('--create-namespace')

    # Add any specified values files to the command.
    for value_file in values:
        helm_command.extend(['--values', value_file])

    click.echo("--------------------------------------------------")
    click.echo(f"Executing command: {' '.join(helm_command)}")
    click.echo("--------------------------------------------------")

    # --- Execute the Helm Command with asyncio ---
    # We use asyncio.create_subprocess_exec to run the command asynchronously.
    try:
        process = await asyncio.create_subprocess_exec(
            *helm_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT  # Redirect stderr to stdout
        )

        # Asynchronously read the output line by line and print it.
        # This provides real-time feedback to the user.
        if process.stdout:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                # The output is in bytes, so we decode it to a string.
                sys.stdout.write(line.decode('utf-8'))
                sys.stdout.flush()

        # Wait for the subprocess to complete and get the return code.
        return_code = await process.wait()

        if return_code:
            # If the command fails, we report an error.
            click.secho(f"\n❌ Error: Helm command failed with exit code {return_code}.", fg='red')
            sys.exit(return_code)

        click.echo("\n--------------------------------------------------")
        click.secho(f"✅  FITA deployed successfully!", fg='green')

    except FileNotFoundError:
        click.secho("\n❌ Error: 'helm' command not found.", fg='red')
        click.echo("Please ensure Helm is installed and in your system's PATH.")
        sys.exit(1)
    except Exception as e:
        click.secho(f"\n❌ An unexpected error occurred: {e}", fg='red')
        sys.exit(1)


# Add commands to the 'framework' group
framework.add_command(deploy_all)
framework.add_command(deploy_services)
framework.add_command(deploy_continuum)
framework.add_command(deploy_cluster)
framework.add_command(deploy_node)
framework.add_command(create_test_app_description)
framework.add_command(deploy_fita)

cli.add_command(framework)


# -----------------------------------------------------------------------------
# Manage commands (ping, mode)
# -----------------------------------------------------------------------------
@click.group(help="System management commands")
def manage():
    pass


@click.command(help='Ping the system to check liveness')
def ping_agent():
    api_url = f"http://{IP}:{PORT}/manage/ping"
    try:
        response = requests.get(api_url, headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            message = response.json().get("message", "Alive")
            click.secho("✅ Ping Successful!", fg="green")
            click.echo(message)
        else:
            click.secho("❌ Ping failed", fg="red")
    except Exception as e:
        click.secho(f"Ping Exception: {e}", fg='red')


@click.command(help='Set the system mode (0: Normal, 1: ML)')
@click.option('--mode', type=click.IntRange(0, 1), required=True)
def set_mode(mode):
    api_url = f"http://{IP}:{PORT}/manage/mode/{mode}"
    try:
        response = requests.put(api_url, headers={'Content-Type': 'application/json'})
        click.echo(response.json())
    except Exception as e:
        click.secho(f"Mode Switch Failed: {e}", fg='red')


manage.add_command(ping_agent)
manage.add_command(set_mode)
cli.add_command(manage)


# -----------------------------------------------------------------------------
# Agent commands (set-policy, delete-policy)
# -----------------------------------------------------------------------------@click.group()
@click.group(help="Agent management commands")
def agent():
    """Manage policies for agents."""
    pass


policies_configmap = {
    "cluster": "cluster-agents-policies",
    "continuum": "continuum-policies",
    "node": "node-agents-policies"
}


@agent.command(name="set-policy")
@click.option('--agent', type=click.Choice(['cluster', 'continuum', 'node']), required=True,
              help="Agent type to add policy for")
@click.option('--file', 'policy_file', type=click.Path(exists=True), required=True,
              help="Path to the policy file")
def policy_add_or_update(agent, policy_file):
    """Add policy to the specified agent configmap."""

    configmap_name = policies_configmap[agent]
    namespace = "mlsysops-framework"

    try:
        with open(policy_file, 'r') as f:
            content = f.read()
    except Exception as e:
        click.echo(f"Error reading file '{policy_file}': {e}")
        return

    client_k8s = KubernetesLibrary("apps", "v1",
                                   os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
                                   context="karmada-apiserver")
    try:
        # Using the filename as the key in ConfigMap data, or use a fixed key like "policy.py"
        key = policy_file.split("/")[-1]  # just filename, no path

        client_k8s.update_configmap_data(namespace, configmap_name, key, content)
        click.echo(f"Policy added to {agent} agent configmap '{configmap_name}'.")
    except Exception as e:
        click.echo(f"Failed to update ConfigMap: {e}")


@agent.command("delete-policy")
@click.option("--agent", type=click.Choice(["cluster", "continuum", "node"]),
              required=True, help="Agent type to remove a policy from")
@click.argument("name", type=str)
def policy_delete(agent: str, name: str):
    """Delete policy by name for the given agent."""
    configmap_name = policies_configmap[agent]
    namespace = "mlsysops-framework"

    client_k8s = KubernetesLibrary(
        "apps",
        "v1",
        os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
        context="karmada-apiserver",
    )

    try:
        # Read current configmap data (implemented inside your KubernetesLibrary)
        configmap = client_k8s.core_v1_api.read_namespaced_config_map(configmap_name, namespace)

        if not configmap.data or name not in configmap.data:
            click.echo(f"Policy '{name}' not found in configmap '{configmap_name}'.")
            return

        del configmap.data[name]  # delete the policy key

        # Update the configmap with the modified data
        client_k8s.core_v1_api.replace_namespaced_config_map(configmap_name, namespace, configmap)
        client_k8s.annotate_pod()
        click.echo(f"Policy '{name}' deleted from {agent} agent policies.")
    except Exception as e:
        click.echo(f"Failed to delete policy: {e}")


configmap_map = {
    "cluster": "cluster-agents-config",
    "continuum": "continuum-agent-config",
    "node": "node-agents-config",
}


@agent.command("set-config")
@click.option("--agent", type=click.Choice(["cluster", "continuum", "node"]))
@click.option("--file", "config_file", type=click.Path(exists=True), required=True, help="Path to the config file")
def set_config(agent: str, config_file: str):
    """Add or update a config entry in the specified agent configmap."""
    configmap_name = configmap_map[agent]
    namespace = "mlsysops-framework"

    try:
        with open(config_file, "r") as f:
            content = f.read()
    except Exception as e:
        click.echo(f"Error reading file '{config_file}': {e}")
        return

    client_k8s = KubernetesLibrary(
        "apps",
        "v1",
        os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
        context="karmada-apiserver",
    )

    try:
        key = os.path.basename(config_file)
        client_k8s.update_configmap_data(namespace, configmap_name, key, content)
        click.echo(f"Config '{key}' added or updated in {agent} agent configmap '{configmap_name}'.")
    except Exception as e:
        click.echo(f"Failed to update ConfigMap: {e}")


@agent.command("delete-config")
@click.option("--agent", type=click.Choice(["cluster", "continuum", "node"]))
@click.argument("key", type=str)
def delete_config(agent: str, key: str):
    """Delete a config entry from the specified agent configmap."""
    configmap_name = configmap_map[agent]
    namespace = "mlsysops-framework"

    client_k8s = KubernetesLibrary(
        "apps",
        "v1",
        os.getenv("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml"),
        context="karmada-apiserver",
    )

    try:
        configmap = client_k8s.core_v1_api.read_namespaced_config_map(configmap_name, namespace)

        if not configmap.data or key not in configmap.data:
            click.echo(f"Config key '{key}' not found in configmap '{configmap_name}'.")
            return

        del configmap.data[key]

        client_k8s.core_v1_api.replace_namespaced_config_map(configmap_name, namespace, configmap)

        click.echo(f"Config key '{key}' deleted from {agent} agent configmap '{configmap_name}'.")
    except Exception as e:
        click.echo(f"Failed to delete config: {e}")


cli.add_command(agent)

if __name__ == "__main__":
    cli()

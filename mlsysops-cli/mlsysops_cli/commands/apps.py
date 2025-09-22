# mlsysops_cli/commands/apps.py
import os
import json
import yaml
import click
import requests

from mlsysops_cli.config import BASE
from mlsysops_cli.utils.ui import rule, info, ok, warn, err, table_kv
from mlsysops_cli.utils.alias import AliasedGroup  # your alias-aware group
from mlsysops_cli.utils.response import handle_response  # 🆕 unified response handling

# Map short aliases to real command names (hidden in --help)
APPS_ALIASES = {
    "ls": "list-all",
    "gs": "get-status",
    "gd": "get-details",
    "gp": "get-performance",
    "rm": "remove",
}

@click.group(cls=AliasedGroup, aliases=APPS_ALIASES, help="Application lifecycle commands")
def apps():
    """Top-level 'apps' command group."""
    pass


# -----------------------------------------------------------------------------
# deploy (long)
# -----------------------------------------------------------------------------
@click.command(name="deploy", help="Deploy an application from YAML or URI")
@click.option('--path', type=click.Path(exists=True), required=False, help='Path to the application YAML file')
@click.option('--uri', type=str, required=False, help='URI to get the YAML description from')
def deploy_app(path: str | None, uri: str | None):
    api_endpoint = f"{BASE}/apps/deploy"

    if path and uri:
        err('Provide only --path or --uri.')
        raise SystemExit(2)
    if not (path or uri):
        err('You must provide --path or --uri.')
        raise SystemExit(2)

    rule("🚀 Deploy Application", "cyan")
    try:
        if path:
            info(f"Reading YAML: {path}")
            with open(path, "r", encoding="utf-8") as f:
                payload = yaml.safe_load(f)
        else:
            info(f"Fetching YAML: {uri}")
            r = requests.get(uri, timeout=30)
            r.raise_for_status()
            payload = yaml.safe_load(r.text)

        resp = requests.post(api_endpoint, json=payload, headers={'Content-Type': 'application/json'})
        # pretty success (AppID + Status), robust error handling (422/detail/etc.)
        data = handle_response(
            resp,
            success_title="DESCRIPTION UPLOADED SUCCESSFULLY!",
            success_fields=[("app_id", "AppID"), ("status", "Status")],
            payload=payload,   # enables typo hints on 422
        )

    except requests.exceptions.RequestException as rexc:
        err(f"Network Error: {rexc}")
        raise SystemExit(1)
    except Exception as e:
        err(f"Error: {e}")
        raise SystemExit(1)

apps.add_command(deploy_app)


# -----------------------------------------------------------------------------
# list-all (long) + hidden alias: ls
# -----------------------------------------------------------------------------
@click.command(name="list-all", help="Returns the system applications status")
def list_all():
    api_url = f"{BASE}/apps/list_all/"
    rule("📋 Applications Status", "magenta")
    try:
        resp = requests.get(api_url, headers={'Accept': 'application/json'})
        if 200 <= resp.status_code < 300:
            data = resp.json()
            system_status = data.get("System_status", {})
            if not system_status:
                warn("No applications found.")
                return
            # show as a neat Key/Value table
            table_kv(list(system_status.items()), title="System Applications")
        else:
            handle_response(resp)  # prints and exits with proper code
    except requests.exceptions.RequestException as rexc:
        err(f"Connection Error: {rexc}")
        raise SystemExit(1)

apps.add_command(list_all)


# -----------------------------------------------------------------------------
# get-status (long) + hidden alias: gs
# -----------------------------------------------------------------------------
@click.command(name="get-status", help="Get application status")
@click.argument('app_id')
def get_app_status(app_id: str):
    api_url = f"{BASE}/apps/status/{app_id}"
    rule(f"🛰️ Status for {app_id}", "cyan")
    try:
        resp = requests.get(api_url, headers={'Accept': 'application/json'})
        if 200 <= resp.status_code < 300:
            try:
                data = resp.json()
            except ValueError:
                data = json.loads(resp.text)
            table_kv(
                [("AppId", data.get('app_id', 'Unknown')), ("Status", data.get('status', 'Unknown'))],
                title="Application Status",
            )
        else:
            handle_response(resp)
    except requests.exceptions.RequestException as rexc:
        err(f"Connection Error: {rexc}")
        raise SystemExit(1)

apps.add_command(get_app_status)


# -----------------------------------------------------------------------------
# get-details (long) + hidden alias: gd
# -----------------------------------------------------------------------------
@click.command(name="get-details", help="Get application details")
@click.argument('app_id')
def get_app_details(app_id: str):
    api_url = f"{BASE}/apps/apps/details/{app_id}"  # matches your backend path
    rule(f"🔎 Details for {app_id}", "cyan")
    try:
        resp = requests.get(api_url, headers={'Accept': 'application/json'})
        if 200 <= resp.status_code < 300:
            try:
                d = resp.json()
            except ValueError:
                d = json.loads(resp.text)

            table_kv([("AppId", d.get('app_id', '?')), ("State", d.get('state', '?'))], title="App")
            # Components: print raw JSON for now (you can render a richer table later)
            components = d.get('components', [])
            if components:
                click.echo(json.dumps(components, indent=2))
            else:
                warn("No component details reported.")
        else:
            handle_response(resp)
    except requests.exceptions.RequestException as rexc:
        err(f"Connection Error: {rexc}")
        raise SystemExit(1)

apps.add_command(get_app_details)


# -----------------------------------------------------------------------------
# get-performance (long) + hidden alias: gp
# -----------------------------------------------------------------------------
@click.command(name="get-performance", help="Get application performance metrics")
@click.argument('app_id')
def get_app_performance(app_id: str):
    api_url = f"{BASE}/apps/performance/{app_id}"
    rule(f"📈 Performance for {app_id}", "cyan")
    try:
        resp = requests.get(api_url, headers={'Accept': 'application/json'})
        if 200 <= resp.status_code < 300:
            try:
                metrics = resp.json()
            except ValueError:
                err("Failed to parse JSON response")
                raise SystemExit(2)

            rows = []
            if isinstance(metrics, list):
                for m in metrics:
                    if isinstance(m, list) and len(m) == 2:
                        name, data = m
                        val = data.get('value', 'N/A') if isinstance(data, dict) else "No Data"
                        rows.append((name, val))

            if rows:
                table_kv(rows, title=f"Metrics for {app_id}")
            else:
                # your API sometimes returns {"message": "..."} when no data.json
                if isinstance(metrics, dict) and metrics.get("message"):
                    warn(metrics["message"])
                else:
                    warn("No metrics")
        else:
            handle_response(resp)
    except requests.exceptions.RequestException as rexc:
        err(f"Connection Error: {rexc}")
        raise SystemExit(1)

apps.add_command(get_app_performance)


# -----------------------------------------------------------------------------
# remove (long) + hidden alias: rm
# -----------------------------------------------------------------------------
@click.command(name="remove", help="Remove application")
@click.argument('app_id')
def remove_app(app_id: str):
    api_url = f"{BASE}/apps/remove/{app_id}"
    rule(f"🧹 Remove {app_id}", "yellow")
    try:
        resp = requests.delete(api_url, json={'app_id': app_id}, headers={'Content-Type': 'application/json'})
        if 200 <= resp.status_code < 300:
            try:
                d = resp.json()
            except Exception:
                d = {"app_id": app_id, "message": "Application status updated to 'To_be_removed'."}
            table_kv([("AppId", d.get("app_id", app_id)), ("Message", d.get("message", "To_be_removed"))], title="Removal")
        else:
            handle_response(resp)
    except requests.exceptions.RequestException as rexc:
        err(f"Connection Error: {rexc}")
        raise SystemExit(1)

apps.add_command(remove_app)

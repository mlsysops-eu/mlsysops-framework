import click
import requests

from mlsysops_cli.config import BASE
from mlsysops_cli.utils.ui import rule, ok, err, table_kv
from mlsysops_cli.utils.alias import AliasedGroup

MANAGE_ALIASES = {
    "p": "ping",
    "sm": "set-mode",
}

@click.group(cls=AliasedGroup, aliases=MANAGE_ALIASES,
             help="System management commands")
def manage():
    pass


@manage.command(name="ping", help="Ping the system to check liveness (short: p)")
def ping_agent():
    api_url = f"{BASE}/manage/ping"
    rule("🔔 Ping", "cyan")
    try:
        resp = requests.get(api_url, headers={'Content-Type': 'application/json'})
        if resp.status_code == 200:
            message = resp.json().get("message", "Alive")
            ok("Ping Successful!")
            table_kv([("message", message)], title="Ping")
        else:
            err("Ping failed")
    except Exception as e:
        err(f"Ping Exception: {e}")


@manage.command(name="set-mode", help="Set the system mode (0: Normal, 1: ML) (short: sm)")
@click.option('--mode', type=click.IntRange(0, 1), required=True)
def set_mode(mode):
    api_url = f"{BASE}/manage/mode/{mode}"
    try:
        resp = requests.put(api_url, headers={'Content-Type': 'application/json'})
        try:
            payload = resp.json()
        except Exception:
            payload = {"response": resp.text}
        table_kv(list(payload.items()), title="Mode Response")
    except Exception as e:
        err(f"Mode Switch Failed: {e}")

import os
import json
import click
import requests
from typing import Optional

from mlsysops_cli.config import BASE
from mlsysops_cli.utils.ui import err, ok
from mlsysops_cli.utils.alias import AliasedGroup
from mlsysops_cli.config import BASE_ML
@click.group(help="ML registry, training, deployments, and inference")
def ml():
    pass

# ----------------- helpers -----------------
def _post_json(url, payload):
    return requests.post(url, json=payload, headers={'Content-Type': 'application/json'})

def _print_response(resp, success_msg="OK"):
    try:
        data = resp.json()
    except Exception:
        data = {"response": resp.text}
    if 200 <= resp.status_code < 300:
        ok(success_msg)
        click.echo(json.dumps(data, indent=2))
    else:
        detail = data.get("detail", resp.text)
        err(f"ERROR [{resp.status_code}]: {detail}")

def _parse_json_arg(ctx, param, value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception as e:
        raise click.BadParameter(f"Invalid JSON: {e}")

# ================= model =================
MODEL_ALIASES = {
    "up": "upload",
    "ls": "list",
    "upd": "update",
    "del": "remove",
}

@ml.group(cls=AliasedGroup, aliases=MODEL_ALIASES, help="Model registry operations")
def model():
    pass

@model.command("add", help="Register model metadata (POST /model/add)")
@click.option("--data", callback=_parse_json_arg, required=True,
              help='JSON string, e.g. \'{"modelname":"Ridge","modelkind":"Regressor"}\'')
def model_add(data):
    url = f"{BASE}/model/add"
    resp = _post_json(url, data)
    _print_response(resp, "Model metadata created")

@model.command("upload", help="Upload an artifact for a model (POST /model/{id}/upload) (short: up)")
@click.argument("model_id", type=str)
@click.option("--file", "file_path", type=click.Path(exists=True), required=True)
@click.option("--kind", "file_kind", type=click.Choice(["model", "data", "code", "env"]), required=True)
def model_upload(model_id, file_path, file_kind):
    url = f"{BASE}/model/{model_id}/upload"
    with open(file_path, "rb") as f:
        files = {
            "file": (os.path.basename(file_path), f, "application/octet-stream"),
            "file_kind": (None, file_kind),
        }
        resp = requests.post(url, files=files)
    _print_response(resp, "File uploaded")

@model.command("list", help="List models (GET /model/all) (short: ls)")
@click.option("--skip", default=0, show_default=True, type=int)
@click.option("--limit", default=100, show_default=True, type=int)
def model_list(skip, limit):
    url = f"{BASE}/model/all"
    resp = requests.get(url, params={"skip": skip, "limit": limit}, headers={"Accept": "application/json"})
    _print_response(resp, "Models fetched")

@model.command("kind", help="List models by kind (GET /model/getkind/{modelkind})")
@click.argument("modelkind", type=str)
def model_kind(modelkind):
    url = f"{BASE}/model/getkind/{modelkind}"
    resp = requests.get(url, headers={"Accept": "application/json"})
    _print_response(resp, f"Models of kind '{modelkind}' fetched")

@model.command("search", help="Search models by tags (GET /model/search?tags=...)")
@click.option("--tag", "tags", multiple=True, help="Repeatable. Example: --tag fast --tag accuracy-focused")
def model_search(tags):
    url = f"{BASE}/model/search"
    params = [("tags", t) for t in tags] if tags else None
    resp = requests.get(url, params=params, headers={"Accept": "application/json"})
    _print_response(resp, "Search results")

@model.command("update", help="Update model metadata (PATCH /model/{id}) (short: upd)")
@click.argument("model_id", type=str)
@click.option("--data", callback=_parse_json_arg, required=True,
              help='Partial JSON, e.g. \'{"modeltags":["updated-tag"]}\'')
def model_update(model_id, data):
    url = f"{BASE}/model/{model_id}"
    resp = requests.patch(url, json=data, headers={'Content-Type': 'application/json'})
    _print_response(resp, "Model updated")

@model.command("remove", help="Delete a model (DELETE /model/{id}) (short: del)")
@click.argument("model_id", type=str)
def model_remove(model_id):
    url = f"{BASE}/model/{model_id}"
    resp = requests.delete(url)
    _print_response(resp, "Model deleted")

# ================= train =================
TRAIN_ALIASES = {
    "st": "add",  # start
}

@ml.group(cls=AliasedGroup, aliases=TRAIN_ALIASES, help="Model training")
def train():
    pass

@train.command("add", help="Start a training job (POST /mltraining/add) (short: st)")
@click.option("--data", callback=_parse_json_arg, required=True,
              help='JSON, e.g. \'{"modelid":"1234","placement":{"clusterID":"*","node":"*","continuum":false}}\'')
def train_add(data):
    url = f"{BASE}/mltraining/add"
    resp = _post_json(url, data)
    _print_response(resp, "Training started")

# ================= deploy =================
DEPLOY_ALIASES = {
    "ls": "list",
    "st": "status",
    "del": "remove",
}

@ml.group(cls=AliasedGroup, aliases=DEPLOY_ALIASES, help="Deployments & operations")
def deploy():
    pass

@deploy.command("list", help="List deployments (GET /deployment/all) (short: ls)")
@click.option("--skip", default=0, show_default=True, type=int)
@click.option("--limit", default=100, show_default=True, type=int)
def deploy_list(skip, limit):
    url = f"{BASE}/deployment/all"
    resp = requests.get(url, params={"skip": skip, "limit": limit}, headers={"Accept": "application/json"})
    _print_response(resp, "Deployments fetched")

@deploy.command("add", help="Create a deployment (POST /deployment/add)")
@click.option("--data", callback=_parse_json_arg, required=True,
              help='JSON, e.g. \'{"modelid":"1234","ownerid":"agent-1","placement":{"clusterID":"*","node":"*","continuum":true},"deployment_id":"dep-5678","inference_data":1}\'')
def deploy_add(data):
    url = f"{BASE}/deployment/add"
    resp = _post_json(url, data)
    _print_response(resp, "Deployment created")

@deploy.command("status", help="Get deployment status (GET /deployment/get/status/{id}) (short: st)")
@click.argument("deployment_id", type=str)
def deploy_status(deployment_id):
    url = f"{BASE}/deployment/get/status/{deployment_id}"
    resp = requests.get(url, headers={"Accept": "application/json"})
    _print_response(resp, "Status fetched")

@deploy.group("ops", help="Deployment operations history")
def deploy_ops():
    pass

@deploy_ops.command("add", help="Record an inference operation (POST /deployment/add/operation)")
@click.option("--data", callback=_parse_json_arg, required=True,
              help='JSON, e.g. \'{"ownerid":"agent-1","deploymentid":"dep-5678","modelid":"1234","data":"{}","result":"{}"}\'')
def deploy_ops_add(data):
    url = f"{BASE}/deployment/add/operation"
    resp = _post_json(url, data)
    _print_response(resp, "Operation recorded")

@deploy_ops.command("list", help="List operations by owner (GET /deployment/get/opos/{ownerid})")
@click.argument("ownerid", type=str)
def deploy_ops_list(ownerid):
    url = f"{BASE}/deployment/get/opos/{ownerid}"
    resp = requests.get(url, headers={"Accept": "application/json"})
    _print_response(resp, "Operations fetched")

@deploy.command("remove", help="Delete a deployment (DELETE /deployment/{id}) (short: del)")
@click.argument("deployment_id", type=str)
def deploy_remove(deployment_id):
    url = f"{BASE}/deployment/{deployment_id}"
    resp = requests.delete(url)
    _print_response(resp, "Deployment deleted")

# ================= infer =================
INFER_ALIASES = {
    "pred": "predict",
}

@ml.group(cls=AliasedGroup, aliases=INFER_ALIASES, help="Inference")
def infer():
    pass

@infer.command("predict", help="Predict (and optionally explain) via deployment_id (short: pred)")
@click.argument("deployment_id", type=str)
@click.option("--data", callback=_parse_json_arg, required=True,
              help='JSON, e.g. \'{"data": [[5.1, 3.5, 1.4, 0.2]], "explain": true}\'')
def infer_predict(deployment_id, data):
    url = f"{BASE}/deployment/{deployment_id}/predict"
    resp = _post_json(url, data)
    _print_response(resp, "Prediction response")

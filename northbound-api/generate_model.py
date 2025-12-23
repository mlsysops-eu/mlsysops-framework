#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import yaml

try:
    # Python 3.9+
    from importlib.resources import files as res_files
except ImportError:  # pragma: no cover
    # Python 3.8 fallback
    from importlib_resources import files as res_files  # type: ignore


CRD_PACKAGE = "mlsysops.crds"
CRD_FILENAME = "MLSysOpsApplication.yaml"
CRD_FILENAME_CLUSTER = "MLSysOpsCluster.yaml"


def _load_crd_yaml_from_package() -> dict:
    """
    Load CRD YAML from python package resources: mlsysops.crds/MLSysOpsApplication.yaml
    Returns parsed YAML as dict.
    """
    resource = res_files(CRD_PACKAGE).joinpath(CRD_FILENAME)
    if not resource.is_file():
        raise FileNotFoundError(f"CRD resource not found: {CRD_PACKAGE}/{CRD_FILENAME}")

    with resource.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _convert_crd_dict_to_jsonschema(crd: dict) -> tuple[str, dict]:
    """
    Convert CRD dict to a JSON Schema dict, wrapped under a root key based on spec.names.kind.
    Returns (root_key, full_schema_dict).
    """
    # Extract kind from spec.names.kind
    root_key: Optional[str] = None
    if (
        isinstance(crd, dict)
        and isinstance(crd.get("spec"), dict)
        and isinstance(crd["spec"].get("names"), dict)
        and isinstance(crd["spec"]["names"].get("kind"), str)
    ):
        root_key = crd["spec"]["names"]["kind"]

    if not root_key:
        raise ValueError("Could not determine 'kind' from CRD → spec.names.kind.")

    # Find openAPIV3Schema under spec.versions[*].schema.openAPIV3Schema
    openapi_schema = None
    versions = crd.get("spec", {}).get("versions")
    if isinstance(versions, list):
        for version in versions:
            if (
                isinstance(version, dict)
                and isinstance(version.get("schema"), dict)
                and "openAPIV3Schema" in version["schema"]
            ):
                openapi_schema = version["schema"]["openAPIV3Schema"]
                break

    if openapi_schema is None:
        raise ValueError("No valid 'openAPIV3Schema' found in the CRD under spec.versions[].schema.")

    # Build full JSON Schema
    full_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": f"{root_key} Schema",
        "type": "object",
        "properties": {
            root_key: openapi_schema
        },
        "required": [root_key],
    }
    return root_key, full_schema


def _run_datamodel_codegen(json_schema_file: str, output_model_file: str) -> None:
    """
    Invoke datamodel-codegen to turn the JSON Schema into a Pydantic model.
    """
    cmd = [
        "datamodel-codegen",
        "--input", json_schema_file,
        "--input-file-type", "jsonschema",
        "--output", output_model_file,
    ]
    try:
        subprocess.check_call(cmd)
    except FileNotFoundError as e:
        raise RuntimeError(
            "'datamodel-codegen' not found. Install it with: pip install datamodel-code-generator"
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"datamodel-codegen failed: {e}") from e


def generate_pydantic_schemas(
    schemas_dir: str | os.PathLike = "schemas",
    output_filename: str = "mlsysops_application.py",
) -> Path:
    """
    Public method to be called from your bootstrap/main.

    - Loads CRD from mlsysops.crds.MLSysOpsApplication.yaml
    - Generates JSON Schema (temp file)
    - Runs datamodel-codegen
    - Writes model into `schemas_dir/output_filename`
    - Ensures schemas_dir exists
    Returns the Path of the generated file.
    """
    crd = _load_crd_yaml_from_package()
    _, schema = _convert_crd_dict_to_jsonschema(crd)

    schemas_path = Path(schemas_dir)
    schemas_path.mkdir(parents=True, exist_ok=True)

    out_file = schemas_path / output_filename

    with tempfile.NamedTemporaryFile(suffix="_schema.json", delete=False) as tmp:
        json_schema_path = tmp.name

    try:
        with open(json_schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)

        _run_datamodel_codegen(json_schema_path, str(out_file))
        return out_file
    finally:
        try:
            os.remove(json_schema_path)
        except OSError:
            pass

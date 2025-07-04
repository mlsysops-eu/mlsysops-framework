#!/usr/bin/env python3
import os
import sys
import glob
import tempfile
import yaml
import json
import subprocess
from jsonschema import validate, ValidationError

def find_single_crd_yaml(crd_dir: str):
    """
    Look for exactly one .yaml or .yml file inside crd_dir.
    Return its full path. Exit if none (or zero).
    If more than one, pick the first and print a warning.
    """
    patterns = [os.path.join(crd_dir, "*.yaml"), os.path.join(crd_dir, "*.yml")]
    matches = []
    for p in patterns:
        matches.extend(glob.glob(p))

    if not matches:
        print(f"[✗] No .yaml/.yml file found under '{crd_dir}'.")
        sys.exit(1)
    if len(matches) > 1:
        print(f"[!] Multiple CRD files found under '{crd_dir}'. Using the first:\n    {matches[0]}")
    return matches[0]

def convert_yaml_crd_to_json(yaml_file: str, json_file: str):
    """
    Converts a YAML CRD schema into a JSON schema file and adds necessary metadata,
    including a root key derived from the CRD schema.
    """
    try:
        with open(yaml_file, 'r') as f:
            yaml_content = yaml.safe_load(f)
        # Extract kind from spec.names.kind
        root_key = None
        if (
            isinstance(yaml_content, dict)
            and 'spec' in yaml_content
            and isinstance(yaml_content['spec'], dict)
            and 'names' in yaml_content['spec']
            and isinstance(yaml_content['spec']['names'], dict)
            and 'kind' in yaml_content['spec']['names']
        ):
            root_key = yaml_content['spec']['names']['kind']

        if root_key is None:
            raise ValueError("Could not determine 'kind' from CRD → spec.names.kind.")

        # Find openAPIV3Schema under spec.versions[*].schema.openAPIV3Schema
        openapi_schema = None
        if (
            'spec' in yaml_content
            and isinstance(yaml_content['spec'], dict)
            and 'versions' in yaml_content['spec']
            and isinstance(yaml_content['spec']['versions'], list)
        ):
            for version in yaml_content['spec']['versions']:
                if (
                    isinstance(version, dict)
                    and 'schema' in version
                    and isinstance(version['schema'], dict)
                    and 'openAPIV3Schema' in version['schema']
                ):
                    openapi_schema = version['schema']['openAPIV3Schema']
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
            "required": [root_key]
        }

        with open(json_file, 'w') as f:
            json.dump(full_schema, f, indent=4)
        print(f"[✓] JSON Schema written to: {json_file}")

    except Exception as e:
        print(f"[✗] Error converting YAML→JSON: {e}")
        sys.exit(1)

def run_datamodel_codegen(json_schema_file: str, output_model_file: str):
    """
    Invoke datamodel-codegen to turn the JSON Schema into a Pydantic model.
    """
    cmd = [
        "datamodel-codegen",
        "--input", json_schema_file,
        "--input-file-type", "jsonschema",
        "--output", output_model_file
    ]
    try:
        print(f"[>] Running: {' '.join(cmd)}")
        subprocess.check_call(cmd)
        print(f"[✓] Model written to: {output_model_file}")
    except FileNotFoundError:
        print("[✗] 'datamodel-codegen' not found. Please install it (pip install datamodel-code-generator).")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[✗] datamodel-codegen failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
    CRD_DIR = os.path.join(SCRIPT_DIR, "input")
    OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

    # 1) Find the single .yaml/.yml in CRD_DIR
    crd_yaml_path = find_single_crd_yaml(CRD_DIR)

    # 2) Ensure output folder exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 3) Create a temporary file for the JSON Schema
    with tempfile.NamedTemporaryFile(suffix="_schema.json", delete=False) as tmp:
        json_schema_path = tmp.name

    # 4) Convert CRD YAML → JSON Schema
    convert_yaml_crd_to_json(crd_yaml_path, json_schema_path)

    # 5) Run datamodel-codegen → output/model.py
    model_py_path = os.path.join(OUTPUT_DIR, "model.py")
    run_datamodel_codegen(json_schema_path, model_py_path)

    # 6) Remove the temporary JSON Schema file
    try:
        os.remove(json_schema_path)
    except OSError:
        pass

    print("\nDone. Your Pydantic model is here:")
    print(f"    {model_py_path}")

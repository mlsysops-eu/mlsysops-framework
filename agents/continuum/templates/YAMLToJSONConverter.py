import yaml
import json
from jsonschema import validate, ValidationError
import argparse


def convert_yaml_crd_to_json(yaml_file: str, json_file: str):
    """
    Converts a YAML CRD schema into a JSON schema file and adds necessary metadata,
    including a root key derived from the CRD schema.

    Args:
        yaml_file (str): Path to the input YAML file containing the CRD schema.
        json_file (str): Path to the output JSON file.
    """
    try:
        # Read and parse YAML file
        with open(yaml_file, 'r') as f:
            yaml_content = yaml.safe_load(f)

        # Extract the root key (kind of the CRD, e.g., MLSysOpsCluster)
        root_key = None
        if 'spec' in yaml_content and 'names' in yaml_content['spec'] and 'kind' in yaml_content['spec']['names']:
            root_key = yaml_content['spec']['names']['kind']
        if root_key is None:
            raise ValueError("Could not determine the root key (kind) from the YAML CRD schema.")

        # Navigate to the `openAPIV3Schema` schema section
        openapi_schema = None
        if ('spec' in yaml_content
                and 'versions' in yaml_content['spec']
                and isinstance(yaml_content['spec']['versions'], list)):
            for version in yaml_content['spec']['versions']:
                if 'schema' in version and 'openAPIV3Schema' in version['schema']:
                    openapi_schema = version['schema']['openAPIV3Schema']
                    break

        if openapi_schema is None:
            raise ValueError("No valid `openAPIV3Schema` found in the CRD file.")

        # Build the full JSON schema with extra metadata
        full_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": f"{root_key} Schema",
            "type": "object",
            "properties": {
                root_key: openapi_schema  # Root key is a property of the object
            },
            "required": [root_key]  # Root key is required
        }

        # Write the full JSON schema to a file
        with open(json_file, 'w') as f:
            json.dump(full_schema, f, indent=4)

        print(f"JSON schema successfully written to {json_file}")

    except Exception as e:
        print(f"Error occurred: {e}")

def validate_yaml_against_schema(yaml_file: str, json_schema_file: str):
    """
    Validates a YAML file against a JSON schema.

    Args:
        yaml_file (str): Path to the YAML file to validate.
        json_schema_file (str): Path to the JSON schema file.

    Raises:
        ValidationError: If the YAML file does not conform to the JSON schema.
    """
    try:
        # Read the YAML file to validate
        with open(yaml_file, 'r') as f:
            yaml_data = yaml.safe_load(f)

        # Read the JSON schema
        with open(json_schema_file, 'r') as f:
            schema = json.load(f)

        # Validate the YAML data against the JSON schema
        validate(instance=yaml_data, schema=schema)
        print(f"The YAML file '{yaml_file}' is valid according to the schema '{json_schema_file}'.")
    except ValidationError as ve:
        print(f"Validation Error: {ve.message}")
    except Exception as e:
        print(f"Error: {e}")

#example usage
if __name__ == "__main__":
    # Command-line argument parsing
    # python script.py convert crd_schema.yaml --schema crd_schema.json
    # python script.py validate input.yaml --schema crd_schema.json

    parser = argparse.ArgumentParser(description="Convert a YAML CRD schema to JSON schema and validate a YAML file against it.")
    parser.add_argument("command", choices=["convert", "validate"], help="The operation to perform: 'convert' or 'validate'.")
    parser.add_argument("input", help="Input YAML file (CRD schema for 'convert'; YAML to validate for 'validate').")
    parser.add_argument("--schema", help="Schema JSON file for validation or output file for conversion.")
    args = parser.parse_args()

    if args.command == "convert":
        # Convert the YAML CRD schema to a JSON schema
        if not args.schema:
            print("Error: You must specify an output file for the JSON schema using --schema.")
        else:
            convert_yaml_crd_to_json(args.input, args.schema)
    elif args.command == "validate":
        # Validate a YAML file against a JSON schema
        if not args.schema:
            print("Error: You must specify the JSON schema file for validation using --schema.")
        else:
            validate_yaml_against_schema(args.input, args.schema)

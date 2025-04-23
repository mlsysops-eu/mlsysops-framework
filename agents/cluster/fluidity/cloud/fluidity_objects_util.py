#/usr/bin/python3
"""Descriptions-related utilities module."""
from __future__ import print_function
import json
import logging
import os
import sys

from jsonschema import Draft7Validator
from ruamel.yaml import YAML

from fluidity_crds_config import CRDS_INFO_LIST


logger = logging.getLogger(__name__)


_JSON_EXT = '.json'
_YAML_EXT = '.yaml' #'.yml'

# be aware in case of import - os.path.dirname(os.path.abspath(__file__))
# sys.path.append('./crds/')


def uncaught_exception_handler(exc_type, exc_value, exc_traceback):
    """Log uncaught exceptions."""
    #logger.exception('Uncaught exception')
    logger.error('Uncaught exception',
                 exc_info=(exc_type, exc_value, exc_traceback))

# Install uncaught exceptions handler
sys.excepthook = uncaught_exception_handler


def get_crd_info(rtype):
    """Check if resource type is valid and get info.

    Args:
        rtype (str): The requested resource type

    Returns:
        (bool, dict), True/False if rtype valid/invalid and
        crd is the respective item from CRDS_INFO_LIST or None.
    """
    rtype = rtype.lower()
    found = False
    crd_info = None
    for crd in CRDS_INFO_LIST:
        # if rtype == crd['singular'] or rtype == crd['plural']:
        if rtype in (crd['singular'], crd['plural']):
            found = True
            crd_info = crd
            break
    return found, crd_info


def get_json_schema(rtype):
    """Get the json schema of a resource type.

    Args:
        rtype (str): The resource type

    Returns:
        dict: The respective python dictionary, empty denotes unknown resource.
    """
    schema = {}
    schema_fname = None
    rtype = rtype.lower()
    found, crd_info = get_crd_info(rtype)
    if not found:
        logger.error('Invalid resource type: %s', rtype)
        return {}
    try:
        with open(crd_info['json_schema_file'], 'r') as json_f:
            schema = json.load(json_f)
            # logger.debug('Validation schema: %s', schema)
    except IOError:
        logger.error('Schema file not in current dir (%s).', schema_fname)
    return schema


def is_valid_resource(rtype, data):
    """Validate a resource.

    Args:
        rtype (str): The resource type
        data (dict): The respective description data

    Returns:
        bool: True if valid, False otherwise
    """
    logger.info('Check if a resource is valid %s:\n%s', rtype, data)
    rtype = rtype.lower()
    found, crd_info = get_crd_info(rtype)
    if not found:
        logger.error('Invalid resource type: %s', rtype)
        return False

    valid = False
    schema = get_json_schema(rtype)
    if not schema:
        return False
    valid = Draft7Validator(schema).is_valid(data)
    logger.info('Resource is valid: %s', valid)
    if valid:
        return True

    logger.error('Resource invalid (schema file: %s)', crd_info['json_schema_file'])
    validator = Draft7Validator(schema)
    for error in sorted(validator.iter_errors(data), key=str):
        logger.error(error.message)
    return False


def load_resource_file(rtype, filename):
    """Load a resource from a file.

    Reads the description from a file, validates it, and
    creates the respective dictionary.

    Args:
        rtype (str): The resource type
        filename (str): The name of the yaml/json file

    Returns:
        dict: The respective dictionary (or an array of dictionaries in
        case of policies) or NONE if an error occurred.
    """
    # logger.info('Load desc from file: %s', filename)
    logger.info('Load desc from file: %s', os.path.realpath(filename))
    rtype = rtype.upper()
    found, _ = get_crd_info(rtype)
    if not found:
        logger.error('Invalid resource type: %s', rtype)
        return False

    # yaml = YAML()
    # yaml = YAML(typ='unsafe')
    yaml = YAML(typ='safe') # simple dict, not ordered
    # yaml = YAML(typ='safe', pure=True)
    yaml.explicit_start = True
    yaml.explicit_end = True
    yaml.indent(sequence=4, offset=2)

    with open(filename) as yaml_f:
        # data = yaml.load(yaml_f)
        data_list = list(yaml.load_all(yaml_f))
        # yaml.dump(data, sys.stdout)
    # single document case
    if len(data_list) == 1:
        if is_valid_resource(rtype, data_list[0]):
            return data_list[0]
        return None
    # multi-document case
    return_list = []
    for data in data_list:
        if is_valid_resource(rtype, data):
            return_list.append(data)
    if return_list:
        return return_list
    return None


def load_pod_file(filename):
    """Load a pod description from a file.

    Reads the description from a file and creates the respective dictionary.

    Args:
        filename (str): The name of the yaml/json file.

    Returns:
        dict: The respective dictionary or NONE if an error occurred.
    """
    # logger.info('Load pod desc from file: %s', filename)
    logger.info('Load pod desc from file: %s', os.path.realpath(filename))

    # yaml = YAML()
    # yaml = YAML(typ='unsafe')
    yaml = YAML(typ='safe') # simple dict, not ordered
    # yaml = YAML(typ='safe', pure=True)
    yaml.explicit_start = True
    yaml.explicit_end = True
    yaml.indent(sequence=4, offset=2)

    with open(filename) as yaml_f:
        data = yaml.load(yaml_f)
    return data


def dict2yaml(data, yaml_name):
    """Convert dictionary to yaml file.

    Args:
        data (dict): The data to convert
        yaml_name (str): The full path target filename

    Returns:
        str: The full path filename of the created yaml
    """
    yaml = YAML(typ='safe')
    yaml.explicit_start = True
    yaml.explicit_end = True
    yaml.indent(sequence=4, offset=2)
    with open(yaml_name, 'w') as yaml_f:
        yaml.dump(data, yaml_f)
    return yaml_name


def json2yaml(filename, yaml_name):
    """Convert json file to yaml.

    Args:
        filename (str): The json file
        yaml_name (str, optional): The target filename

    Returns:
        str: The full path filename of the created yaml
    """
    # return yaml.dump(json.load(sys.stdin))
    name = os.path.splitext(filename)[0]
    with open(filename, 'r') as json_f:
        data = json.load(json_f)

    dir_path = os.path.dirname(os.path.realpath(filename))
    name = os.path.splitext(os.path.basename(filename))[0]
    if yaml_name is None:
        yaml_name = name + _YAML_EXT
    yaml_name = os.path.join(dir_path, yaml_name)
    yaml = YAML(typ='safe')
    yaml.explicit_start = True
    yaml.explicit_end = True
    yaml.indent(sequence=4, offset=2)
    with open(yaml_name, 'w') as yaml_f:
        yaml.dump(data, yaml_f)
    return yaml_name


def yaml2json(filename, json_name=None):
    """Convert yaml file to json.

    Args:
        filename (str): The yaml file
        json_name (str): The target filename

    Returns:
        str: The full path filename of the created json
    """
    # json.dumps(yaml.load(f))
    # os.path.splitext(os.path.basename(filename))[0]
    yaml = YAML(typ='safe')
    with open(filename, 'r') as yaml_f:
        data = yaml.load(yaml_f)

    dir_path = os.path.dirname(os.path.realpath(filename))
    name = os.path.splitext(os.path.basename(filename))[0]
    if json_name is None:
        json_name = name + _JSON_EXT
    json_name = os.path.join(dir_path, json_name)
    with open(json_name, 'w') as json_f:
        json.dump(data, json_f, indent=2, sort_keys=True)
    return json_name


def test_load(option):
    """Basic resources loading test cases."""
    if option == 'drone':
        status = load_resource_file('drone', 'manifests/drone1.yaml')
        print(status)
    elif option == 'edgenode':
        status = load_resource_file('edgenode', 'manifests/edgenode1.yaml')
        print(status)
    elif option == 'fluidityapp':
        status = load_resource_file('fluidityapp', 'manifests/app1.yaml')
        print(status)
    elif option == 'dronestation':
        status = load_resource_file('dronestation', 'manifests/station1.yaml')
        print(status)
    elif option == 'policies':
        status = load_resource_file('policies', 'manifests/desc_pol.yaml')
        print(status)
        if status is not None:
            for restr in status:
                print(restr)
    elif option == 'invalid_type':
        status = load_resource_file('invalid_type', 'manifests/drone1.yaml')
        print(status)


def test_convert():
    """Format conversion tests."""
    name = 'crds/drone.yaml'
    new_file = yaml2json(name)
    print(new_file)

    new_file = yaml2json(name, 'test_drone.json')
    print(new_file)

    name = 'crds/test_drone.json'
    new_file = json2yaml(name, 'drone_test.yaml')
    print(new_file)


# if __name__ == '__main__':
    # test_load('drone')
    # test_load('edgenode')
    # test_load('dronestation')
    # test_load('fluidityapp')
    # test_load('restrictions')
    # test_load('invalid_type')
    # test_convert()

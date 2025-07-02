#   Copyright (c) 2025. MLSysOps Consortium
#   #
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#   #
#       http://www.apache.org/licenses/LICENSE-2.0
#   #
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#  #
#  #

#/usr/bin/python3
"""Descriptions-related utilities module."""
from __future__ import print_function
import json
import logging
import os
import sys

from jsonschema import Draft7Validator
from ruamel.yaml import YAML
from cluster_config import CRDS_INFO_LIST

from mlsysops.logger_util import logger

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
        if rtype in (crd['singular'], crd['plural']):
            found = True
            crd_info = crd
            break
    return found, crd_info
    

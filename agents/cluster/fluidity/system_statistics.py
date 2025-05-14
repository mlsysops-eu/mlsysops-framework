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
"""Fluidity nodes functionality."""
from __future__ import print_function
import logging
import sys

logger = logging.getLogger(__name__)

def add_statistic_entry(dict_structure, entry_name):
    statistics_dict = {
        'AvgCallDelay': 0.0,
        'RawCallDelays': [],
        'CurrentSum': 0.0,
        'TotalCalls': 0,
        'lastEntrance': 0,
        'lastExit': 0,
        'MigrateFrom': {}
    }
    dict_structure['statistics'][entry_name] = statistics_dict

def add_migration_entry(dict_structure, migration_dst_name, migration_src_name):
    adaptation_dict = {
        'AvgAdaptDelay': 0.0,
        'RawAdaptDelays': [],
        'CurrentSum': 0.0,
        'TotalAdaptations': 0
    }
    dict_structure['statistics'][migration_dst_name]['MigrateFrom'][migration_src_name] = adaptation_dict

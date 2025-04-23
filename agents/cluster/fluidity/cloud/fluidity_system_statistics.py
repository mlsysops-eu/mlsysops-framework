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

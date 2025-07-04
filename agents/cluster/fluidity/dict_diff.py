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

import re


class DeepDiffPathApplier:
    """
    Utility class for applying DeepDiff-style changes to a dictionary.

    This class provides methods to parse path strings, navigate deeply nested
    dictionaries, and apply transformations such as additions, deletions, and value
    changes based on DeepDiff-style paths. It is useful for synchronizing changes
    between data structures or applying patch-like transformations.

    Attributes:
        source: dict
            The source dictionary representing the current state from which paths
            and values will be extracted and applied to a target dictionary.
    """

    def __init__(self, source_dict):
        self.source = source_dict

    def parse_path(self, path):
        """
        Parse a DeepDiff-style path string into a list of keys.
        
        Args:
            path (str): A path string in DeepDiff format (e.g. "['key1'][0]['key2']")
            
        Returns:
            list: A list of keys where string keys are preserved as strings and numeric 
                 indices are converted to integers
        """
        # Matches ['key'] or [0]
        return [int(m[1]) if m[0] == '' else m[0]
                for m in re.findall(r"\['(.*?)'\]|\[(\d+)\]", path)]

    def get_nested(self, keys):
        """
        Get a nested value from the source dictionary using a sequence of keys.

        Args:
            keys (list): A list of keys to traverse the nested dictionary structure

        Returns:
            The value found at the nested location
            
        Raises:
            KeyError: If any key in the path doesn't exist
        """
        curr = self.source
        for k in keys:
            curr = curr[k]
        return curr

    def set_nested(self, target_dict, keys, value):
        """
        Set a value in a nested dictionary structure, creating intermediate dictionaries
        and lists as needed.

        Args:
            target_dict (dict): The dictionary to modify
            keys (list): A sequence of keys defining the nested path
            value: The value to set at the specified path
        """
        curr = target_dict
        for k in keys[:-1]:
            if isinstance(k, int):
                while len(curr) <= k:
                    curr.append({})
                curr = curr[k]
            else:
                curr = curr.setdefault(k, {})
        last_key = keys[-1]
        if isinstance(last_key, int):
            while len(curr) <= last_key:
                curr.append({})
            curr[last_key] = value
        else:
            curr[last_key] = value

    def delete_nested(self, target_dict, keys):
        """
        Delete a value from a nested dictionary structure.

        Args:
            target_dict (dict): The dictionary to modify
            keys (list): A sequence of keys defining the path to the value to delete
        """
        curr = target_dict
        for k in keys[:-1]:
            curr = curr[k]
        last_key = keys[-1]
        if isinstance(curr, list) and isinstance(last_key, int):
            if 0 <= last_key < len(curr):
                curr.pop(last_key)
        elif last_key in curr:
            del curr[last_key]

    def apply_added_paths(self, target_dict, added_paths):
        """
        Apply additions from source to target dictionary based on provided paths.

        Args:
            target_dict (dict): The dictionary to modify
            added_paths (set): Set of paths for items to be added
        """
        for path in added_paths:
            keys = self.parse_path(path)
            value = self.get_nested(keys)
            self.set_nested(target_dict, keys, value)

    def remove_deleted_paths(self, target_dict, deleted_paths):
        """
        Remove items from target dictionary based on provided paths.

        Args:
            target_dict (dict): The dictionary to modify
            deleted_paths (set): Set of paths for items to be deleted
        """
        for path in deleted_paths:
            keys = self.parse_path(path)
            self.delete_nested(target_dict, keys)

    def apply_value_changes(self, target_dict, value_changes):
        """
        Apply value changes to target dictionary based on change specifications.

        Args:
            target_dict (dict): The dictionary to modify
            value_changes (dict): Dictionary mapping paths to change specifications
                                containing 'new_value' keys
        """
        for path, change in value_changes.items():
            keys = self.parse_path(path)
            self.set_nested(target_dict, keys, change['new_value'])

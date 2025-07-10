# Mechanisms

## Fluidity
* In this version, the supported actions are: (i) `deploy`, (ii) `move`, 
(iii) `remove`, (iv) `change_spec`. Below we document the expected format of each action.
* Deploy: `{'action': 'deploy', 'host': node_name}`
(deploy component on node with hostname `node_name`, which can 
also be retrieved from the respective MLSysOpsNode description).
* Move: `{'action': 'move', 'target_host': node_name_1, 'src_host': node_name_2}` 
(relocate component from `node_name_2` to `node_name_1`).
* Remove: `{'action': 'remove', 'host': node_name}`
(remove component from node with hostname `node_name`).
* Change spec: `{'action': 'change_spec', 'new_spec': updated_spec, 'host': node_name}`
(Change component specification on node `node_name` to the new spec `updated_spec` that follows
the same structure as the respective component description that are used in MLSysOpsApp resources).
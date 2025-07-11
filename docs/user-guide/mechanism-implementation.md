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

* The `new_plan` dictionary must be comprised of the the following keys:
    * `deployment_plan`: It is the desired plan to be executed by Fluidity. The value is also a 
    dictionary with the component names as keys (only those that adaptation should occur) 
    and the respective value is a list of actions to be made for this component (see above).
    * `initial_plan`: A boolean flag, indicating whether the plan refers to the initial deployment
    of the component(s) or not.

Also refer to [policy plugins](../design/plugins/policy_plugins.md) and [policy implementation](policy-implementation.md) docs.
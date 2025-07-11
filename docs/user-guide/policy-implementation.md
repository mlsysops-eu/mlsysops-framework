# Initial deployment and adaptation policy reference

This section provides three indicative examples of different policies for (i) static component placement,
(ii) component relocation and (iii) component specification modification. Also refer to [Policy plugins doc](../design/plugins/policy_plugins.md).
---

## Example `policy-staticPlacement.py`
`initial_plan()` reads the application description and places the components to the respective hosts
if specified. If the none of the components has fixed node requirements, an empty plan is returned.

```python
""" Plugin function to implement the initial deployment logic.
"""
def initial_plan(context, app_desc, system_desc):
    # Store app name and description in context
    context['name'] = app_desc['name']
    context['spec'] = app_desc['spec']

    # Set initial plan flag to True so that analyze() can trigger plan()
    if 'initial_deployment_finished' not in context:
        context['initial_deployment_finished'] = True

    # Store app component names
    context['component_names'] = []
    plan = {}

    for component in app_desc['spec']['components']:
       
        comp_name = component['metadata']['name']
        logger.info('component %s', comp_name)
        context['component_names'].append(comp_name)
        node_placement = component.get("node_placement", None)
        if node_placement:
            node_name = node_placement.get("node", None)
            # If node has static placement requirement, add action to plan
            if node_name:
                plan[comp_name] = [{'action': 'deploy', 'host': node_name}]

    return plan, context
```

`analyze()` just triggers `plan()` at the first invocation. All the subsequent calls will return False.
```python
async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    # Retrieve the first application from the list
    application = application_description[0]
    adaptation = False
    
    # The first time that analyze is called, set flag to True
    if 'initial_deployment_finished' not in context:
        logger.info('initial deployment not finished')
        adaptation = True

    return adaptation, context
```
If `initial_plan()` has returned the first plan, return it to Fluidity for execution. Otherwise, no 
adaptation occurs (empty plan).
```python
async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    plan_result = {}
    plan_result['deployment_plan'] = {}
    application = application_description[0]
    description_changed = False


    if 'initial_deployment_finished' not in context:
        initial_plan_result, new_context = initial_plan(context, application, system_description)
        if initial_plan_result:
            plan_result['deployment_plan'] = initial_plan_result
            plan_result['deployment_plan']['initial_plan'] = True

    if plan_result['deployment_plan']:
        plan_result['name'] = context['name']
       
    new_plan = {
        "fluidity": plan_result
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context
```

## Example `policy-relocateComponents.py`
This policy relocates (deploys a new component instance on a host and removes the old one),
for demo purposes, based on custom logic that invokes `plan()` with configurable frequency.
This happens only for components that do not have strict placement requirements (node is not specified
via the app description).

Setup the initial context of the policy using `initialize()` function.
```python
def initialize():
    print(f"Initializing policy {inspect.stack()[1].filename}")

    initialContext = {
        "telemetry": {
            "metrics": ["node_load1"],
            "system_scrape_interval": "5s"
        },
        "mechanisms": [
            "fluidity_proxy"
        ],
        "packages": [],
        "configuration": {
            "analyze_interval": "10s"
        },
        "latest_timestamp": None,
        "core": False,
        "scope": "application",
        "current_placement": None,
        "initial_deployment_finished": False,
        "moving_interval": "30s",
        "dynamic_placement_comp": None
    }

    return initialContext
```

`parse_analyze_interval()` converts the key stored in context to seconds in order to
manually set the frequency of `plan()` invocation.
```python
def parse_analyze_interval(interval: str) -> int:
    """
    Parses an analyze interval string in the format 'Xs|Xm|Xh|Xd' and converts it to seconds.

    Args:
        interval (str): The analyze interval as a string (e.g., "5m", "2h", "1d").

    Returns:
        int: The interval in seconds.

    Raises:
        ValueError: If the format of the interval string is invalid.
    """
    # Match the string using a regex: an integer followed by one of s/m/h/d
    match = re.fullmatch(r"(\d+)([smhd])", interval)
    if not match:
        raise ValueError(f"Invalid analyze interval format: '{interval}'")

    # Extract the numeric value and the time unit
    value, unit = int(match.group(1)), match.group(2)

    # Convert to seconds based on the unit
    if unit == "s":  # Seconds
        return value
    elif unit == "m":  # Minutes
        return value * 60
    elif unit == "h":  # Hours
        return value * 60 * 60
    elif unit == "d":  # Days
        return value * 24 * 60 * 60
    else:
        raise ValueError(f"Unsupported time unit '{unit}' in interval: '{interval}'")
```

`initial_plan()` checks for components without fixed placement requirements and produces
the initial deployment plan.


```python
""" Plugin function to implement the initial deployment logic.
"""
def initial_plan(context, app_desc, system_description):
    logger.info('initial deployment phase ', app_desc)

    context['name'] = app_desc['name']
    context['spec'] = app_desc['spec']
    context['initial_deployment_finished'] = True
    context['component_names'] = []
    plan = {}

    # Random host selection to relocate between two nodes of the cluster
    context['main_node'] = system_description['MLSysOpsCluster']['nodes'][0]
    context['alternative_node'] = system_description['MLSysOpsCluster']['nodes'][1]
    # Retrieve the first node of the node list.
    context["current_placement"] = system_description['MLSysOpsCluster']['nodes'][0]

    for component in app_desc['spec']['components']:
        comp_name = component['metadata']['name']
        logger.info('component %s', comp_name)
        context['component_names'].append(comp_name)
        node_placement = component.get("node_placement")
        if node_placement:
            node_name = node_placement.get("node", None)
            if node_name:
                logger.info('Found node name. Will continue')
                continue
        context['dynamic_placement_comp'] = comp_name
        plan[comp_name] = [{'action': 'deploy', 'host': context["current_placement"]}]
    logger.info('Initial plan %s', plan)
    return plan, context
```

`analyze()` periodically triggers adaptation based on manual configuration in `context['moving_interval']`.
```python
async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    logger.info(f"\nTelemetry {telemetry}")
    
    current_timestamp = time.time()

    # The first time called
    if context['latest_timestamp'] is None:
        context['latest_timestamp'] = current_timestamp
        return True, context

    # All the next ones, get it
    analyze_interval = parse_analyze_interval(context['moving_interval'])
    if current_timestamp - context['latest_timestamp'] > analyze_interval:
        context['latest_timestamp'] = current_timestamp
        return True, context

    return False, context
```

`plan()` checks the current host and relocates to the other node.
```python
async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    #logger.info(f"Called relocation plan  ----- {mechanisms}")
    
    context['initial_plan'] = False
    
    plan_result = {}
    plan_result['deployment_plan'] = {}
    application = application_description[0]
    
    if 'initial_deployment_finished' in context and context['initial_deployment_finished'] == False:
        initial_plan_result, new_context = initial_plan(context, application, system_description)
        if initial_plan_result:
            plan_result['deployment_plan'] = initial_plan_result
            plan_result['deployment_plan']['initial_plan'] = True

            comp_name = new_context['dynamic_placement_comp']
    else:
        comp_name = context['dynamic_placement_comp']
        plan_result['deployment_plan']['initial_plan'] = False
        plan_result['deployment_plan'][comp_name] = []
        curr_plan = {}

        if context['main_node'] == context["current_placement"]:
            curr_plan = {
                "action": "move",
                "target_host": context['alternative_node'],
                "src_host": context['main_node'],
            }
            context["current_placement"] = context['alternative_node']
        elif context['alternative_node'] == context["current_placement"]:
            curr_plan = {
                "action": "move",
                "target_host": context['main_node'],
                "src_host": context['alternative_node'],
            }
            context["current_placement"] = context['main_node']
        
        plan_result['deployment_plan'][comp_name].append(curr_plan)
    

    if plan_result:
        plan_result['name'] = context['name']

    new_plan = {
        "fluidity": plan_result,
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context
```


## Example `policy-changeCompSpec.py`
This policy performs component specification change at runtime.
We showcase 3 different changes based on:
(i) Kubernetes Pod runtime class name.
(ii) Container image used.
(iii) Pod resource requirements (cpu and memory).

```python
spec_changes = cycle([
    {'runtime_class_name': cycle(['crun', 'nvidia'])},
    {'image': cycle(['harbor.nbfc.io/mlsysops/test-app:sha-90e0077', 'harbor.nbfc.io/mlsysops/test-app:latest'])},
    {'platform_requirements': {
            'cpu': { 
                'requests': '', # in m
                'limits': '' # in m
            },
            'memory': {
                'requests':  '', # in Mi
                'limits':  '' # in Mi
            }
        }
    }
])
```

```python
def initialize():
    print(f"Initializing policy {inspect.stack()[1].filename}")

    initialContext = {
        "telemetry": {
            "metrics": ["node_load1"],
            "system_scrape_interval": "1s"
        },
        "mechanisms": [
            "fluidity_proxy"
        ],
        "packages": [],
        "configuration": {
            "analyze_interval": "30s"
        },
        "latest_timestamp": None,
        "core": False,
        "scope": "application",
        "curr_comp_idx": 0,
        "current_placement": None,
        "initial_deployment_finished": False,
        "moving_interval": "30s",
        "dynamic_placement_comp": None
    }

    return initialContext
```

```python
async def analyze(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    current_timestamp = time.time()

    # The first time called
    if context['latest_timestamp'] is None:
        context['latest_timestamp'] = current_timestamp
        return True, context

    # All the next ones, get it
    analyze_interval = parse_analyze_interval(context['moving_interval'])
    logger.info(f"{current_timestamp} - {context['latest_timestamp']}  = {current_timestamp - context['latest_timestamp']} with interval {analyze_interval}")
    
    if current_timestamp - context['latest_timestamp'] > analyze_interval:
        context['latest_timestamp'] = current_timestamp
        return True, context
    
    return True, context
```

`plan()` selects one of the available changes in the component spec (round-robin).
We show change between 2 runtime class names, 2 container images and random component 
resource requirements.
```python
async def plan(context, application_description, system_description, mechanisms, telemetry, ml_connector):
    plan_result = {}
    plan_result['deployment_plan'] = {}
    application = application_description[0]
    description_changed = False
    change_idx = cycle([0, 1, 2])
    curr_change = next(spec_changes)
    cpu_suffix = 'm'
    mem_suffix = 'Mi'

    # Get the first component just for demo purposes
    component = application['spec']['components'][0]
    comp_name = component['metadata']['name']
    logger.info(f'component spec {component}')

    # If the component has fixed node placement requirement find the host
    # else select the first node
    if 'node_placement' in component and 'node' in component['node_placement']:
        node = component['node_placement']['node']
        logger.info(f'Found static placement on {node} for comp {comp_name}')
    else: 
        node = system_description['MLSysOpsCluster']['nodes'][0]
        logger.info(f'Randomly select host {node} for {comp_name}')
    
    plan_result['deployment_plan'][comp_name] = []
    
    for key in curr_change:
        if key == 'runtime_class_name': 
            component[key] = next(curr_change[key])
        else:
            for container in component['containers']:

                if key == 'image':
                    # Find the next image to be used and continue
                    container[key] = next(curr_change[key])
                    continue
                
                # Set random cpu/mem requirements for the component
                request_cpu = str(random.randint(0, 300))
                limit_cpu = str(random.randint(301, 400))

                request_mem = str(random.randint(0, 300))
                limit_mem = str(random.randint(301, 400))
                
                logger.info(f'request_cpu+cpu_suffix {request_cpu+cpu_suffix}')

                if key not in container or 'cpu' not in container[key] or 'memory' not in container[key]:
                    container[key] = {
                        'cpu': {
                            'requests': '',
                            'limits': ''
                        },
                        'memory': {
                            'requests': '',
                            'limits': ''
                        }
                    }

                container[key]['cpu']['requests'] = request_cpu+cpu_suffix
                container[key]['cpu']['limits'] = limit_cpu+cpu_suffix

                container[key]['memory']['requests'] = request_mem+mem_suffix
                container[key]['memory']['limits'] = limit_mem+mem_suffix

        plan_result['deployment_plan'][comp_name].append({'action': 'change_spec', 'new_spec': component, 'host': node})
        logger.info(f"Applying change type {key} to comp {comp_name}, new spec is {component}")
   
    # If there is a produced plan, extend the plan accordingly with the application name and initial_plan flag
    if plan_result:
        plan_result['name'] = application['name']
        # This policy will only take effect after initial deployment is done.
        plan_result['deployment_plan']['initial_plan'] = False

    new_plan = {
        "fluidity": plan_result
    }
    logger.info('plan: New plan %s', new_plan)

    return new_plan, context
```
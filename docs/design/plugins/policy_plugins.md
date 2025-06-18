# Policy Plugins

Policy plugins are the components responsible for determining if a new adaptation is required and generating new
configuration plans. They follow the MAPE paradigm, specifically implementing the Analyze and Plan tasks. A policy
plugin is implemented as a Python module, which may import and use any external libraries, and must define three
specific methods: (i) initialize, (ii) analyze, and (iii) plan. Each method requires specific arguments and must return
defined outputs. Each method accepts a common argument, context, which can be used to maintain state between different
method calls, as well as across consecutive invocations of the policy plugin. Policy plugins can be bound to a node or
multiple applications; however, they need to decide on at least one mechanism.

The methods are described as follows:

**initialize**: This method contains the initialization configuration required by the agent. It is called during the
plugin
loading phase, and it must return the common context dictionary with specific values. An example is shown in Figure 35,
where the policy declares the telemetry configuration it requires, the mechanisms it will analyze and manage, any custom
Python packages needed by the script, and any additional agent configuration parameters. An important parameter is to
declare if this policy will make use of machine learning - this enables the usage of the ML Connector interface and
accordingly configures the mechanism that enables/disables machine learning usage in the framework.

```python
def initialize(context):
    context = {
        # The required values
        "telemetry": {
            "metrics": ["node_load1"],
            "system_scrape_internval": "1s"
        },
        "mechanisms": [
            "CPUFrequency"
        ],
        "packages": [
            ## Any possible required Python packages needed
        ],
        "configuration": {
            # Agent configuration
            "analyze_interval": "4s"
        },
        "machine_learning_usage": false,
        # ... any other fields that the policy needs
    }

    return context
```

**analyze**: The purpose of this method is to analyze the current state of the system and the target application, and
determine whether a new configuration plan might be required. In the example shown in Figure X, the **analyze** function
compares the current telemetry data for the application—retrieved using the application description—with the target
value specified by the application. If the current value exceeds the defined threshold (target), the method concludes
that a new plan is needed. In this example, it is assumed that the monitored application metric should remain below the
specified target. The analyze method can also make use of the ML Connector interface, to make use of machine learning
models deployed from that service.

```python
def analyze(context, application_description, system_description, current_plan, telemetry, ml_connector):
    # policy that checks if application target is achieved

    if telemetry['data']['application_metric'] > application_description['targets']['application_metric']:
        return True, context  # It did not achieve the target - a new plan is needed      

    return False, context
```

**Figure X. Analyze method example**

**plan**: This method decides if a new plan is needed, and if it is positive, generates a new configuration plan based
on all available information in the system, including application and system descriptions, telemetry data, the current
plan, and available assets. It may also leverage the ML Connector interface to invoke machine learning models. In the
example shown in Figure X, the plan method creates a new configuration for the CPU frequency of the node on which it
runs. If the application target is not met, the method sets the CPU to the maximum available frequency; otherwise, it
sets it to the minimum. The configuration values used in the plan are predefined and known to the policy developer,
based on the specifications of the corresponding mechanism plugin (see Section 2.4.2 for examples).

```python
def plan(context, application_description, system_description, current_plan, telemetry, ml_connector
         , available_assets):
    if telemetry['data']['application_metric'] > application_description['targets']['application_metric']:
        cpu_frequency_command = {
            "command": "set",
            "cpu": "all",
            "frequency": "max"
        }
    else:
        cpu_frequency_command = {
            "command": "set",
            "cpu": "all",
            "frequency": "min"
        }

    if new_plan != current_plan:
        new_plan = {
            "CPUFrequency": cpu_frequency_command
        }
        return new_plan, context

    return current_plan, context
```

**Figure X. Plan method example**

For both the `analyze` and `plan` methods, the arguments are as follows *(subject to change, and actual values are
documented at the opensource documentation - see Section Y (os))*:

- **application\_descriptions**: A dictionary or a list of dictionaries containing values from the submitted
  applications in the system (see Section X).
- **system\_description**: A dictionary containing system information provided by the system administrator (see Section
  X).
- **current\_plan**: The currently active plan for this policy. Since a previously generated plan may have failed, this
  argument allows the policy plugin to handle such scenarios appropriately.
- **telemetry**: A dictionary containing telemetry data from both the system and the applications.
- **ml\_connector**: An object handler providing access to the ML Connector service endpoint within the slice. This
  argument is empty if the ML Connector service is not available \[\*\]\[see documentation\].

As described in Section 2.1, the above plugin methods are invoked and executed within the respective Analyze and Plan
tasks. The Plan Scheduler ensures that any conflicts between different policy-generated plans are resolved and forwards
them to the Execute tasks, which utilize the mechanism plugins to apply the configuration to the system. The declaration
of machine learning model usage for each plugin enables MLSysOps to track where and when machine learning mechanisms are
employed, monitor their performance, and disable plugins that utilize AI tools if requested. The plug-and-play support
further allows for the dynamic modification of configuration logic, enabling agents to adapt to varying operational
scenarios.
The primary responsibility of the agents is to manage the system’s assets—entities and components that can be configured
and/or must be monitored. Typical assets include application components, available configuration mechanisms, and the
telemetry system. The MAP tasks continuously monitor the state of these assets, analyze their condition, determine
whether a new configuration plan is required, and, if so, create and execute the plan using the mechanism plugins. The
Analyze and Plan tasks invoke the logic implemented in the policy plugins, whereas the Execution task uses the mechanism
plugins.

## Monitor
The Monitor task runs periodically, collecting information from the environment and updating the agent's internal state.
This information is sourced from the telemetry system, external mechanisms (via Southbound API mechanism plugins), and
other external entities (e.g., other agents). Although there is only a single instance of the Monitor task, it is
adaptive; its configuration can change at runtime based on the agent’s current requirements. A fundamental configuration
parameter is the frequency and type of information retrieved from the telemetry system. For example, when a new
application is submitted to the system, additional telemetry metrics may need to be collected and incorporated into the
internal state.

## Analyze
For each distinct managed asset, a separate Analyze task thread runs periodically. This thread invokes the corresponding
method of the active policy plugin (see Section 8.3.1) for the specific asset, supplying all necessary inputs, including
telemetry data and relevant system information (e.g., application and system descriptions). Policy plugins may implement
the analysis logic using simple heuristics or employ machine learning models, either through the MLSysOps ML Connector
or via any external service. This task also includes core logic to perform basic failure checks in the event of errors
arising within the policy plugins.
The output of the Analyze task is a binary value (True or False), indicating whether a new configuration plan is
required for the analyzed asset. If the result is True, a new Plan task is initiated.

## Plan
The Plan task is responsible for generating a new configuration plan and is executed once for each positive result
produced by the Analyze task. The planning logic, implemented by the policy plugins, is invoked upon trigger and
receives all necessary input data.
The output of this task is a dictionary containing values expected by each mechanism plugin. This dictionary represents
the configuration plan to be applied by the respective configuration mechanisms. The result is pushed into a queue and
forwarded to the Plan Scheduler (see Section 8.1.5).

## Execute
This task is invoked by the Plan Scheduler (see Section 8.1.5) once for each mechanism that must be configured in a
given plan. Based on the dictionary provided by the plan, the corresponding mechanism plugin is called and supplied with
the relevant configuration data. The new configuration is applied using a best-effort approach, without any retry logic,
and the outcome is logged into the state (see Section 8.1.6). In the event of an error, it is expected that the
subsequent run of the Analyze task will detect the issue and handle it appropriately.

## Plan Scheduler
Each agent supports the concurrent activation of multiple policy and mechanism plugins. As a result, different policies
may generate configuration plans for the same mechanism simultaneously. This situation can lead to conflicts during plan
execution, where multiple plans attempt to apply different—and potentially conflicting—configuration changes to the same
mechanism at the same time. To handle such conflicts, the MLSysOps agent includes a Plan Scheduler module that processes
the queued plans produced by Plan tasks (see Section 8.1.3) in a FIFO manner. The first plan in the queue is applied,
and any subsequent plan targeting a mechanism already configured by a previous plan is discarded. The Plan Scheduler is
designed to be extensible, allowing support for more advanced scheduling policies in the future.
For each scheduled plan, a single Execute task (see Section 8.1.4) is launched to apply the new configuration.

## State
This is the internal state (memory) of the agents. Each agent contains different information depending on its
environment (continuum level, node type etc.). Some indicative information needed to be kept are information about the
application descriptions as well as system and application telemetry. It is able to store historical snapshots of the
telemetry data that has been acquired by the monitor task
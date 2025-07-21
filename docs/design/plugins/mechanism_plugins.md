The MLSysOps framework does not impose assumptions about the underlying system architecture, recognizing that real-world
infrastructures often consist of heterogeneous systems with varying adaptation capabilities and operational
requirements. Different types of nodes offer different configuration options, and nodes operating at higher levels of
the continuum (e.g., cluster or continuum nodes) have distinct configuration needs. To ensure seamless
integration—especially with the policy plugins—MLSysOps defines a standardized plugin interface for system
administrators and mechanism providers, known as **mechanism plugins**.

To develop a mechanism plugin, a Python script must be provided, implementing three methods: (i) `apply`, (ii)
`get_status`, and (iii) `get_options`. The plugin module may use any required libraries, and it is assumed that any
necessary packages are pre-installed along with the agent.

The methods are defined as follows \[*footnote: examples refer to CPU frequency control on a node*\]:

**apply**: This is the primary method invoked by an Execute task. It accepts a single argument, `command`, which is a
dictionary whose structure is defined and documented by the mechanism plugin. This dictionary is produced by the `plan`
method of a policy plugin. The policy developer must be familiar with the available mechanism plugins in the system and
the expected format of the `command` argument. Figure X shows an example of a CPU configuration plugin that utilizes
supporting libraries, as described in Section 3.2. The expected dictionary structure is documented in the method’s
comment section, followed by the call to the underlying library to apply the specified configuration.

```python
def apply(command: dict[str, any]):
    """
    Applies the given CPU frequency settings based on the provided parameters.

    This method modifies the CPU's frequency settings by either applying the changes across
    all CPUs or targeting a specific CPU. The modifications set a new minimum and maximum
    frequency based on the input values.

    Args:
        command (dict):
         {
            "command": "reset" | "set",
            "cpu": "all" | "0,1,2...",
            "frequency" : "min" | "max" | "1000000 Hz"
        }
    """
    # The rest of the code omitted 
    cpufreq.set_frequencies(command['frequency'])
    # .....
```

**Figure X. CPU Frequency configuration mechanism plugin (apply method).**

**get\_status:** This method must return any available relevant status of the underlying mechanism. Figure X, shows the
CPU frequency configuration mechanism plugin, the method return the current frequencies of all the CPU cores. This is
used by the Monitoring and Execute task, to observe the general status of the mechanism. The mechanism provider may not
implement this method, and opt-in to push the state into the telemetry stream.

```python
def get_status():
    """
    Retrieves the current CPU frequencies.

    Returns:
        list: A list of integers representing the current frequencies of the CPU cores. The
        frequencies are usually measured in MHz.
    """
    return get_cpu_current_frequencies()
```

**Figure X. CPU Frequency mechanism status method.**

**get\_options:** It returns the available configuration options for the mechanism that is handled by the plugin. In the
example in Figure X, it returns the available CPU frequency steps, that can be used as values in the *frequency* key of
the command dictionary of the apply method. This is meant to be used in a development environment, where MLSysOps
framework provides suitable logging methods.

```python
def get_options():
    """
    Retrieves the list of CPU available frequencies.

    Returns:
        list: A list of frequencies supported by the CPU.
    """
    return get_cpu_available_frequencies()
```

**Figure X. CPU Frequency mechanism status method.**

The relationship and interaction between the policy and mechanism plugins are demonstrated in section 2.4.4.
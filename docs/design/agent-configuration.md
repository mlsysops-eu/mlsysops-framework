Each agent uses a configuration file that defines its behaviour during instantiation. While agents operating at
different layers of the continuum instantiate different components of the core MLSysOps framework, all agents running on
nodes use the same base instance. However, since node characteristics may vary significantly, each agent can be
individually configured using its corresponding configuration file.

```YAML
telemetry:
  default_metrics: 
      - "node_load1"
  monitor_data_retention_time: 30
  monitor_interval: 10s
  managed_telemetry:
    enabled: True

policy_plugins:
  directory: "policies"

mechanism_plugins:
  directory: "mechanisms"
  enabled_plugins:
   - "CPUFrequencyConfigurator"

continuum_layer: "node"

system_description: 'descriptions/rpi5-1.yaml'

behaviours:
  APIPingBehaviour:
    enabled: False
  Subscribe:
    enabled: False
```
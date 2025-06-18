# MLSysOps Telemetry SDK & API

The MLSysOps framework offers integrators two pathways to interface with the telemetry system: i) use the OpenTelemetry
SDK and its respective API or ii) employ the MLSysOps Telemetry SDK, which provides a simplified API. The former
provides SDKs for a wide range of programming languages, enabling both manual instrumentation and automated
instrumentation on compatible software systems. The latter serves as a wrapper on top of the OpenTelemetry SDK,
abstracting away all the mundane code required to connect to an OpenTelemetry Collector and push metrics. This
abstraction uses two function calls: one for pushing metrics and one for retrieving metrics. Instrumenting application
components within the MLSysOps Framework is achievable with either of these options. MLSysOps Telemetry API/SDK is
implemented in Python language and is available in the opensource
repository [MLSysOps Python Telemetry Library](https://github.com/mlsysops-eu/MLSysOps-Python-Telemetry-Library).  

## API Reference

TBD
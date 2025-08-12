# MLSysOps Framework

The *MLSysOps Framework* is the open-source outcome of the EU-funded MLSysOps
Horizon Europe project (Grant ID 101092912), running from Jan 2023 to Dec 2025.
Its aim is to deliver an AI-enabled, agent-based platform for autonomic,
cross-layer management of compute, storage, and network resources across cloud,
edge, and IoT environments.

## Key Objectives

- Provide an *open, AI-ready framework* for scalable, trustworthy,
  explainable system operation across heterogeneous infrastructures.
- Enable *continual ML learning* and retraining during runtime via
  hierarchical agents.
- Support *portable, efficient execution* using container innovation and
  modular, FaaS-inspired offloading.
- Promote *green, resource-efficient, and secure operations* while
  maintaining `QoS`/`QoE` targets.
- Facilitate realistic evaluation using real-world deployments in smart-city
  and precision-agriculture scenarios.

## Core Components

- Hierarchical Agent Architecture: Interfaces with orchestration/control
  systems and exposes an ML-model API for plug-and-play explainable/retrainable
  models.

- Telemetry & Control Knobs: Collects metrics across the continuum and adjusts
  configuration (e.g., compute, network, storage, accelerator usage)
  dynamically.

- Distributed FaaS-style Executor: Enables function offloading across tiers to
  optimize latency, energy, and performance.

- Explainable ML & Reinforcement Learning Module: Offers transparent decisions,
  highlighting input factors influencing agent actions.

- Use cases: Includes real applications focusing on smart cities and agriculture.

## Repository Contents

| Directory | Description |
|----------|-------------|
| `agents/` | Core autonomic agents with policy-based plugins and ML/analytics |
| `orchestrators/` | Scripts to facilitate testbed setup |
| `mlsysops-cli/` | Tool to manage MLSysOps-related descriptors (agents, applications, etc.)|
| `northbound-api/` | Glue API from the CLI to the core Agent framework|
| `docs/` | Internal and public-facing documentation |

## Getting Started

### Prerequisites

- Kubernetes v1.26+
- `kubectl`, `karmada`
- Python 3.10+
- Access to a 4-node testbed environment

### Quick Start

Install the CLI tool:

```bash
pip install mlsysops-cli


### Quick Start

Install the CLI tool:

```bash
pip install mlsysops-cli
```

Given an `ansible` inventory to setup 4 nodes in `inv.yml`, you can deploy the framework:

```bash
mls framework deploy-all --inventory inv.yml
```

Create and deploy an example application:

```bash
mls framework create-app-test-description
mls apps deploy-app --path mlsysops-app-test-description.yaml
```

See docs/ for detailed component setup guides.

## Documentation

Check the full documentation at [docs.mlsysops.eu](https://docs.mlsysops.eu)

## Contributing

We welcome contributions from the community!

Browse [good first issues](https://github.com/mlsysops-eu/mlsysops-framework/issues?q=is%3Aissue%20state%3Aopen%20label%3Agood-first-issue)

Review our [CONTRIBUTING.md](https://docs.mlsysops.eu/developer-guide/contribute/)

Follow our [CODE_OF_CONDUCT.md](https://github.com/mlsysops-eu/mlsysops-framework/blob/main/docs/developer-guide/Code-of-Conduct.md)

## License

This project is licensed under the Apache 2.0 License.

## Acknowledgements

This framework is developed as part of the Horizon Europe MLSysOps Project
(Grant ID 101092912), coordinated by the University of Thessaly, with
contributions from 12 European partners across academia and industry.

Learn more at [mlsysops.eu](https://mlsysops.eu)

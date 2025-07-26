# MLSysOps Framework

The **MLSysOps Framework** is the open-source result of the Horizon Europe _MLSysOps_ project (Grant ID 101092912), running from Jan 2023 to Dec 2025. It delivers an AI-enabled, agent-based platform for autonomic, cross-layer management of compute, storage, and network resources across cloud, edge, and IoT environments.

---

## 🚀 Key Objectives

- Provide an **AI-ready, open framework** for scalable and explainable operations across heterogeneous infrastructures.
- Enable **continual ML learning and retraining** at runtime using hierarchical agents.
- Support **portable and efficient execution** via containers and modular, FaaS-style offloading.
- Promote **green, resource-efficient, and secure operations** while maintaining QoS/QoE.
- Enable **realistic evaluation** through deployments in smart city and precision agriculture scenarios.

---

## 🧩 Core Components

- **Hierarchical Agent Architecture**  
  Interfaces with orchestration/control systems and supports plug-and-play ML models.

- **Telemetry & Control Knobs**  
  Collects metrics and dynamically tunes compute, network, storage, and accelerators.

- **Distributed FaaS-style Executor**  
  Offloads functions across layers to optimize latency, energy, and performance.

- **Explainable ML & RL Modules**  
  Provides transparent decision-making and insight into agent behavior.

- **Real-world Use Cases**  
  Includes smart city and precision agriculture applications.

---

## 📁 Repository Structure

| Directory         | Description                                                            |
| ----------------- | ---------------------------------------------------------------------- |
| `agents/`         | Core autonomic agents with policy plugins and ML analytics             |
| `orchestrators/`  | Scripts and tools for testbed orchestration                            |
| `mlsysops-cli/`   | Command Line Interface to manage agents, applications, and deployments |
| `northbound-api/` | API layer connecting CLI with the core framework                       |
| `docs/`           | Design documents, usage guides, and contribution guidelines            |

---

## 🛠️ Getting Started

### Prerequisites

- Kubernetes `v1.26+`
- `kubectl`, `karmada`
- Python `3.10+`
- Access to a 4-node testbed environment

### Quick Start

Install the CLI:

```bash
pip install mlsysops-cli
```

Clone the repository:

```bash
git clone https://github.com/RR-Sahoo/mlsysops-framework.git
cd mlsysops-framework
```

Launch the test environment:

```bash
make deploy-testbed
```

Use the CLI:

```bash
mlsysops-cli --help
```

---

## 🤝 Contributing

We welcome contributions from the community!

- See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.
- Read our [Code of Conduct](docs/CODE_OF_CONDUCT.md).
- For design details, refer to [docs/design-overview.md](docs/design-overview.md).

---

## 👥 Maintainers

The MLSysOps Framework is maintained by:

- [Your Name / Org 1](mailto:your.email@example.com)
- [Your Name / Org 2](mailto:another.email@example.com)

See [MAINTAINERS.md](docs/MAINTAINERS.md) for the full list.

---

## 📄 License

This project is licensed under the Apache 2.0 License. See the [LICENSE](LICENSE) file for details.

---

## 📢 Acknowledgements

This work is funded by the European Union’s Horizon Europe program under Grant Agreement No. 101092912 (MLSysOps).

---

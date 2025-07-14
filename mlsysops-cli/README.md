# MLSysOps CLI (`mls`)
<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-MLSysOps-blue?style=for-the-badge">
  <img alt="Python Version" src="https://img.shields.io/badge/python-3.7+-yellowgreen?style=for-the-badge&logo=python">
  <img alt="PyPI" src="https://img.shields.io/pypi/v/mlsysops-cli?style=for-the-badge&logo=pypi">
</p>

The official command-line interface for the **MLSysOps Framework**. This tool empowers you to manage applications, infrastructure resources, and orchestration agents seamlessly across the device-edge-cloud continuum.

## 📋 Table of Contents

- [✨ Features](#-features)
- [✅ Prerequisites](#-prerequisites)
- [📦 Installation](#-installation)
- [🔧 Configuration](#-configuration)
- [🚀 Quick Start](#-usage)
- [📚 Command Reference](#-command-reference)
  - [Application Commands](#-application-commands)
  - [Infrastructure Commands](#️-infrastructure-commands)
  - [Management Commands](#️-management-commands)
  - [Framework Commands](#-framework-commands)
- [💡 Pro Tip: Enable Tab Completion](#-pro-tip-enable-tab-completion)
- [📄 License](#-license)

---

## ✨ Features

- **📱 Application Management**: Deploy, list, and remove applications with simple commands.
- **🏗️ Infrastructure Insight**: Query and register infrastructure components like clusters and nodes.
- **⚙️ System Control**: Ping system agents and switch operational modes Heuristic or ML.
- **🤖 Agent Deployment**: Easily deploy orchestration agents to nodes, clusters, or an entire continuum.
- **🌐 Framework installation**: Install the required components of the Framework.

---
## ✅ Prerequisites

Before you begin, ensure you have the following installed:
- **Python 3.7+**
- `pip` (Python package installer)

---

## 📦 Installation

You can install the MLSysOps CLI using one of the following methods.

### Option 1: Install from PyPI (Recommended)

```bash
pip install mlsysops-cli
```

After installation, you can use the `mls` command directly in your terminal.

---

### Option 2: Install from source (For Development)

If you plan to contribute to the CLI or need the latest unreleased features, install it from the source repository.

```bash
# 1. Clone the repository (CLI branch)
git clone -b CLI [https://github.com/mlsysops-eu/mlsysops-framework.git](https://github.com/mlsysops-eu/mlsysops-framework.git)

# 2. Navigate to the CLI directory
cd mlsysops-framework/mlsysops-cli

# 3. Install in editable mode
pip install -e .
```

This will also expose the `mls` command in your terminal, and any changes you make to the code will be reflected immediately.

---

## 🔧 Configuration

Make sure you have your environment variables or `.env` file set up with:

```bash
# Configuration with the framework API
export MLS_API_IP=<MLS API host ip>
export MLS_API_PORT=8000

# Deployment
export KARMADA_HOST_KUBECONFIG=<path to karmada host kubeconfig>
export KARMADA_API_KUBECONFIG=<path to karmada api kubeconfig>
export KARMADA_HOST_IP=<karmada host ip>
```


---
## 🚀 Quick Start

Get an overview of all available commands and options with the --help flag.

```bash
mls --help
```

Each major component of the framework has its own command group:

- `mls apps` – Manage application deployments  
- `mls infra` – Query and register infrastructure
- `mls manage` – System control (ping, mode switch)  
- `mls framework` – Deploy the core framework components.

---
# 📚 Command Reference

### 🧹 Application Commands

Manage the lifecycle of your applications 

- **Deploy an application**   
```bash
mls apps deploy-app --path ./my_app.yaml
```
- **List all running applications**   
```bash
mls apps list-all
```
- **Remove an application**   
```bash
mls apps remove-app <application-id>
```





### 🏗️ Infrastructure Commands
Query information about your registered infrastructure.
- **List Infrastructure by type (e.g., Cluster, Node)**  
```bash
mls infra list-infra --type Cluster
```

### ⚙️ Management Commands
Perform system-level administrative tasks.

-**Ping a system agent to check its status:**

```bash
mls manage ping-agent
```
-**Set the system's operational mode:**
0 for Heuristic 1 for ML
```bash
mls manage set-mode --mode 1
```

### 🌐 Framework Commands

Deploy core components of the MLSysOps framework and orchestration agents.

```bash
mls framework deploy-all
mls framework deploy-cluster
mls framework deploy-continuum
mls framework deploy-node
mls framework deploy-services
```

**Optional path argument:** Use the `--path` flag to specify the system descriptions folder.
  ```bash
  mls framework deploy-all/cluster/continuum/node --path ./descriptions
  ```
  The `descriptions` folder should contain subfolders like `node`, `cluster`, or `continuum` for proper agent configuration.

**Optional inventory argument:** Use the `--inventory` flag to specify the inventory YAML file used during the K3s installation.
  ```bash
  mls framework add-system-agents --inventory ./inventory.yaml
  ```

> **Note:** Only one of `--path` or `--inventory` can be specified at a time. If both options are provided, the command will throw an error.
---

## 💡 Pro Tip: Enable Tab Completion

Enable tab-completion for the `mls` CLI in your terminal to quickly discover available commands and options:
This will help you auto-complete commands and options by simply pressing the [TAB] key.

```bash
echo 'eval "$(_MLS_COMPLETE=bash_source mls)"' >> ~/.bashrc
source ~/.bashrc
```

Now you can type mls [TAB][TAB] to see all available commands. It's a game-changer! 🎉

---

## 📄 License

This project is licensed by MLSysOps.

## Copyright © 2025 MLSysOps.

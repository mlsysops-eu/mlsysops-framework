# MLSysOps CLI

**MLSysOps CLI** (`mls`) is a command-line tool for interacting 
with the MLSysOps framework. It allows users to manage applications,
infrastructure resources, and orchestration agents across the 
device-edge-cloud continuum.


## 📦 Installation

Make sure you have **Python 3.7+** and `pip` installed.

### Option 1: Install via pip (recommended)

```bash
pip install -i https://test.pypi.org/simple/ mlsysops-cli
```

After installation, you can use the `mls` command directly in your terminal.

---

### Option 2: Install from source (for development)

If you want to work on the CLI or customize it:

```bash
# Clone the repository (make sure to use the CLI branch)
git clone -b CLI https://github.com/mlsysops-eu/mlsysops-framework.git

# Go into the CLI directory
cd mlsysops-framework/mlsysops-cli

# Install it in editable mode
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
## 🚀 Usage

```bash
mls --help
```

Each section of the system has its own command group:

- `mls apps` – Manage application deployments  
- `mls infra` – Query and register infrastructure
- `mls manage` – System control (ping, mode switch)  
- `mls agents` – Deploy orchestration agents  

---

## 🧹 Application Commands

```bash
mls apps deploy-app --path ./my_app.yaml
mls apps list-all
mls apps remove-app
```

## 🏗️ Infrastructure Commands

```bash
mls infra list-infra --type Cluster
```

## ⚙️ Management Commands

```bash
mls manage ping-agent
mls manage set-mode --mode 1
```

## Framework Commands

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

## ⚡ Tab Completion (Bash)

Enable tab-completion for the `mls` CLI in your terminal to quickly discover available commands and options:


```bash
echo 'eval "$(_MLS_COMPLETE=bash_source mls)"' >> ~/.bashrc
source ~/.bashrc
```

Then try:

```bash
mls [TAB][TAB]
```
Enjoy instant access to commands and flags 🎉

---

## 📄 License

License © 2025 [MLSysOps]

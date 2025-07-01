# MLSysOps CLI

**MLSysOps CLI** (`mls`) is a command-line tool for interacting 
with the MLSysOps framework. It allows users to manage applications,
infrastructure resources, and orchestration agents across the 
device-edge-cloud continuum.

## 📦 Installation

Make sure you have Python 3.7+ and `pip` installed.

```bash
pip install mlsysops-cli
```

This will expose the `mls` command in your terminal.

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

---

## 🔧 Configuration

You can override the default API IP and PORT using environment variables:

```bash
export MLS_API_IP=<MLS API host ip>
export MLS_API_PORT=8000

export KARMADA_HOST_KUBECONFIG=<path to karmada host kubeconfig>
export KARMADA_API_KUBECONFIG=<path to karmada api kubeconfig>
export KARMADA_HOST_IP=<karmada host ip>
```

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

## 🛠️ Development

Clone the repo and install locally:

```bash
git clone https://github.com/mlsysops-eu/mlsysops-framework/tree/CLI
cd mlsysops-cli
pip install -e .
```
## 📜 Changelog

## Version [1.0] - 2025-07-01
First public version of the CLI.
### Description:
- Version tested with the testbed setup. 

### Added
- mls commands 

### Fixed
- .

### Changed
- .

## 📄 License

License © 2025 [Marco Loaiza / MLSysOps]

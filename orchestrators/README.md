Ansible Playbook for k3s and Karmada Installation
=================================================

This document provides a step-by-step guide to using the provided Ansible playbook to install and configure k3s across multiple clusters. Additionally, it includes instructions for setting up Karmada, a multi-cluster management tool.



## Table of Contents

1. [Prerequisites](#prerequisites)  
2. [Installation Steps](#installation-steps)  
   * [Setting Up Ansible](#setting-up-ansible)  
   * [Inventory Configuration](#inventory-configuration)  
   * [k3s Installation Playbook](#k3s-installation-playbook)  
   * [Karmada Installation Playbook](#karmada-installation-playbook)  
  


## Prerequisites
Before proceeding, ensure the following:

- **Ansible Installed:** Install Ansible on the control node.
- **SSH Access:** Ensure the control node has SSH access to all target nodes.
- **Python 3 Installed:** Ensure Python 3 is available on all nodes.
- **Supported OS:** The playbooks are tested on Ubuntu 22.04 LTS. Other Linux distributions may require adjustments.
- **Multiple Machines:** At least one machine for the management cluster (Karmada) and others for k3s clusters (master and worker nodes).

## Installation Steps
To set up Ansible, run the follow commands:

1) Update System Packages to latest version.

    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
2) Install essential packages that Ansible relies on:
    
    ```bash 
    sudo apt install -y python3 software-properties-common
    ```
3) Install Ansible.

    ```bash
    sudo apt install -y ansible
    ```
4) After installation, confirm that Ansible is installed and working correctly by checking its version: 
    ```bash
    ansible --version
    ```
Example output:

```
  ansible 2.10.8
  config file = None
  configured module search path = ['/home/pmavrikos/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = /usr/lib/python3/dist-packages/ansible
  executable location = /usr/bin/ansible
  python version = 3.10.12 (main, Feb  4 2025, 14:57:36) [GCC 11.4.0]
```

### Setting Up Ansible
Once Ansible is installed, you need to set up your project by cloning the repository and configuring the necessary files.


**Clone the Repository and navigate to the project directory**

```bash
git clone https://github.com/mlsysops-eu/mlsysops-framework
cd orchestrators
``` 

### Inventory Configuration
The inventory.yml file contains the list of target nodes where k3s and Karmada will be installed. Before running the playbooks, update this file with your specific setup.


**Understand the Structure**

The file is divided into:
 
- **management_cluster:**  The machine where Karmada will be installed (usually one node).
- **cluster1:** A k3s cluster with:
    - **master_nodes:** Control-plane nodes.
    - **worker_nodes:** Worker nodes that run workloads. 
  
**Mandatory fields to update:**

- `ansible_host`: Replace `xxxxx` with the IP address of each target node.
- `ansible_user`: Enter the SSH username for logging into the machine
- `ansible_ssh_private_key_file`:  Provide the full path to your SSH private key on the control machine. 
- `ansible_python_interpreter`: Ensure it points to a valid Python 3 interpreter path on each target node.
- `k3s_cluster_name`: Specify a meaningful cluster name.
- `pod_cidr` and `service_cidr`: Customize network ranges for pods and services (they must not overlap between clusters).

**Labels**

You can specify node labels for each host in the **inventory.yml** file. These labels are applied to the corresponding nodes during the k3s installation and can be used for scheduling workloads or organizing nodes based on their roles or characteristics.
To add labels, include a labels section under each host with key-value pairs representing the label names and values. For example:

```yaml
labels:
  is_vm: true
  mlsysops/continuumLayer: node
  vaccel: "false"
```
In this setup, labels like `mlsysops/continuumLayer` indicate the layer or role of the node within the MLSysOps architecture:
- `continuum`: Used for management nodes (e.g., in the management cluster).
- `cluster`: Used for master nodes in k3s clusters.
- `node`: Used for worker nodes.

Other labels, such as `is_vm: true` and `vaccel: "false"`, indicate whether the node is a virtual machine or has specific acceleration capabilities enabled, respectively. These labels are particularly useful when managing multiple clusters with Karmada, as they allow for consistent identification and selection of nodes across different clusters for workload scheduling.

After running the `k3s-install.yml` playbook, verify the applied labels by executing:

```bash
kubectl get nodes --show-labels
```

on the control-plane node of each cluster.

**Example Configuration**

```yaml
all:
  children:
    management_cluster: # <-- In this vm will be karmada
      hosts:
        testvm00: # <-- Change with your vm name
          ansible_host: x.x.x.x # <-- Update with the correct IP address
          ansible_user: mlsysops
          ansible_ssh_private_key_file: /home/x.x.x.x/.ssh/id_rsa # <-- Update
          ansible_python_interpreter: /usr/bin/python3
          k3s_cluster_name: management
          pod_cidr: "x.x.x.x/x"
          service_cidr: "x.x.x.x/x"
          labels:
            is_vm: true
            mlsysops/continuumLayer: continuum
            vaccel: "false"

    cluster1:
      children:
        master_nodes:
          hosts:
            testvm1: # <-- Change with your master node vm name
              ansible_host: "x.x.x.x" # <-- Update with the correct IP address
              ansible_user: mlsysops
              ansible_ssh_private_key_file: /home/x.x.x.x/.ssh/id_rsa # <-- Update
              ansible_python_interpreter: /usr/bin/python3
              k3s_cluster_name: cluster1
              pod_cidr: "x.x.x.x/x"
              service_cidr: "x.x.x.x/x"
              labels:
                is_vm: true
                mlsysops/continuumLayer: cluster
                vaccel: "false"
        worker_nodes:
          hosts:
            testvm2:
              ansible_host: x.x.x.x # <-- Update with the correct IP address
              ansible_user: mlsysops
              ansible_ssh_private_key_file: /home/xxxxxxxxx/.ssh/id_rsa # <-- Update
              ansible_python_interpreter: /usr/bin/python3
              k3s_cluster_name: cluster1
              labels:
                is_vm: true
                mlsysops/continuumLayer: node
                vaccel: "false"
            testvm3:
              ansible_host: x.x.x.x # <-- Update with the correct IP address
              ansible_user: mlsysops
              ansible_ssh_private_key_file: /home/xxxxxxxxxxx/.ssh/id_rsa # <-- Update
              ansible_python_interpreter: /usr/bin/python3
              k3s_cluster_name: cluster1
              labels:
                is_vm: true
                mlsysops/continuumLayer: node
                vaccel: "false"
```

**Verify**

After editing inventory.yml, save the file and check it for errors. You can test the inventory with:

```bash
ansible-inventory -i inventory.yml --list
```
This shows all nodes Ansible will target.

### k3s Installation Playbook
The k3s-install.yml playbook automates the deployment of a multi-node k3s cluster.

- Ensure the inventory file is updated before running the playbook.
- Execute the playbook to install k3s across all defined nodes.
- After installation, the kubeconfig file for each cluster is stored at:
```
/home/<ANSIBLE_USER>/.kube/config
```
on the control-plane node.

To run [k3s-install.yml](k3s-install.yml) playbook, use the following command:
```bash
ansible-playbook -i inventory.yml k3s-install.yml
```

### Karmada Installation Playbook
The karmada-install.yml playbook sets up Karmada, a multi-cluster management system.

To run [karmada-install.yml](karmada-install.yml), playbook, use the following command:
```bash
ansible-playbook -i inventory.yml karmada-install.yml
```




# Basic Testbed

To install the MLSysOps framework, you will need one or more kubernetes clusters, acting as the compute nodes (cloud / edge layers) and a management node (or cluster), acting as the high-level orchestrator. In the following document we provide the necessary steps to bootstrap an example testbed.

## Quick links

[Prerequisites](#prerequisites)  
[Installation Steps](#installation-steps)  
[Setting Up Ansible](#setting-up-ansible)  
[Inventory Configuration](#inventory-configuration)  
[k3s Installation Playbook](#k3s-installation-playbook)  
[Karmada Installation Playbook](#karmada-installation-playbook)  
  
## Prerequisites
Before proceeding, ensure the following:

- **Ansible Installed:** Install Ansible on the control node.
- **SSH Access:** Ensure the control node has SSH access to all target nodes.
- **Python 3 Installed:** Ensure Python 3 is available on all nodes.
- **Supported OS:** The playbooks are tested on Ubuntu 22.04 LTS. Other Linux distributions may require adjustments.
- **Multiple Machines:** At least one machine for the management cluster (Karmada) and others for k3s clusters (master and worker nodes).

Assuming we have bootstrapped a **control node** that will manage the testbed installation, we can proceed.

## Installation Steps
To set up Ansible, run the follow commands on the control node:

1) Update System Packages to latest version.

```
sudo apt update && sudo apt upgrade -y
```
2) Install essential packages that Ansible relies on:
    
```
sudo apt install -y python3 software-properties-common
```
3) Install Ansible.

```
sudo apt install -y ansible
```
4) After installation, confirm that Ansible is installed and working correctly by checking its version: 
```
ansible --version
```
Example output:

```console
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

```
git clone https://github.com/mlsysops-eu/mlsysops-framework
cd mlsysops-framework
``` 

### Inventory Configuration
The inventory.yml file contains the list of target nodes where k3s and Karmada will be installed. Before running the playbooks, update this file with your specific setup.


**Understand the Structure**

The file is divided into:
 
- **management_cluster:**  The machine where Karmada will be installed (usually one node).
- **cluster1:** A k3s cluster with:
    - **master_nodes:** Control-plane nodes (you can have one or more for high availability).
    - **worker_nodes:** Worker nodes that run workloads. 
  
**Mandatory fields to update:**

- `ansible_host`: Replace `xxxxx` with the IP address of each target node.
- `ansible_user`: Enter the SSH username for logging into the machine
- `ansible_ssh_private_key_file`:  Provide the full path to your SSH private key on the control machine. 
- `ansible_python_interpreter`: Ensure it points to a valid Python 3 interpreter path on each target node.
- `k3s_cluster_name`: Specify a meaningful cluster name.
- `pod_cidr` and `service_cidr`: Customize network ranges for pods and services (they must not overlap between clusters).

**Example Configuration**

```
all:
  children:
    management_cluster: # <-- In this vm will be karmada
      hosts:
        mls00: # <-- Change with your vm name
          ansible_host: x.x.x.x   # <-- Update with the correct IP address
          ansible_user: mlsysops
          ansible_ssh_private_key_file: /home/xxxxxx/.ssh/id_rsa # <-- Update
          ansible_python_interpreter: /usr/bin/python3
          k3s_cluster_name: management
          pod_cidr: "x.x.x.x/x"
          service_cidr: "x.x.x.x/x"

    cluster1:
      children:
        master_nodes:
          hosts:
            mls01: # <-- Change with your master node vm name
              ansible_host: x.x.x.x   # <-- Update with the correct IP address
              ansible_user: mlsysops 
              ansible_ssh_private_key_file: /home/xxxxxxxx/.ssh/id_rsa  # <-- Update
              ansible_python_interpreter: /usr/bin/python3
              k3s_cluster_name: cluster1
              pod_cidr: "x.x.x.x/x"
              service_cidr: "x.x.x.x/x"
        worker_nodes:
          hosts:
            mls02:
              ansible_host: x.x.x.x # <-- Update with the correct IP address
              ansible_user: mlsysops
              ansible_ssh_private_key_file: /home/xxxxxxxxx/.ssh/id_rsa  # <-- Update
              ansible_python_interpreter: /usr/bin/python3
              k3s_cluster_name: cluster1
            mls03:
              ansible_host:  x.x.x.x # <-- Update with the correct IP address
              ansible_user: mlsysops
              ansible_ssh_private_key_file: /home/xxxxxxxxxxx/.ssh/id_rsa # <-- Update
              ansible_python_interpreter: /usr/bin/python3
              k3s_cluster_name: cluster1
```

**Verify**

After editing inventory.yml, save the file and check it for errors. You can test the inventory with:

```
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
```
ansible-playbook -i inventory.yml k3s-install.yml
```

### Karmada Installation Playbook
The karmada-install.yml playbook sets up Karmada, a multi-cluster management system.

To run [karmada-install.yml](karmada-install.yml), playbook, use the following command:
```
ansible-playbook -i inventory.yml karmada-install.yml
```


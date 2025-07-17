#!/usr/bin/env python3

import subprocess
import time
import yaml
import json
import sys

# VM definitions
vms = [
    {"name": "sysops01", "target": "base01"},
    {"name": "sysops02", "target": "base01"},
    {"name": "sysops03", "target": "dell00"},
    {"name": "sysops04", "target": "dell01"},
]

project = "mlsysops"
remote = "nbfc:"
profile = "mlsysops-vms"
image = "images:ubuntu/22.04/cloud"

# Map to inventory groups
vm_cluster_map = {
    "sysops04": "management_cluster",
    "sysops01": "sysops01.master_nodes",
    "sysops02": "sysops01.worker_nodes",
    "sysops03": "sysops01.worker_nodes",
}

if len(sys.argv) > 1 and sys.argv[1] != 'skip' or len(sys.argv) == 1:
    
    # 1. Launch the VMs
    for vm in vms:
        name = vm["name"]
        print(f"Launching VM: {name}")
        try:
            subprocess.run([
                "incus", "launch", image, f"{remote}{name}",
                "--vm",
                "-c", "limits.cpu=4",
                "-c", "limits.memory=6GiB",
                "--project", project,
                "--target", vm["target"],
                "--profile", profile
            ], check=True)
        except subprocess.CalledProcessError:
            print(f"Failed to launch {name}", file=sys.stderr)
            continue
    
    # 2. Wait a bit for VMs to boot and acquire IPs
    print("Waiting 20 seconds for VMs to initialize networking...")
    time.sleep(20)

# 3. Fetch all instance info
print("📡 Fetching VM information from Incus...")
output = subprocess.check_output([
    "incus", "list", remote, "--format", "json", "--project", project
]).decode()
instances = json.loads(output)

# 4. Build the inventory
inventory = {"all": {"children": {}}}

for inst in instances:
    name = inst["name"]
    if name not in vm_cluster_map:
        continue

    # Traverse group path
    cluster_path = vm_cluster_map[name].split(".")
    group = inventory["all"]["children"]
    for part in cluster_path[:-1]:
        group = group.setdefault(part, {}).setdefault("children", {})
    final_group = group.setdefault(cluster_path[-1], {}).setdefault("hosts", {})

    # Look for 192.168.5.X address
    ip_address = None
    for net in inst["state"]["network"].values():
        if isinstance(net, dict) and "addresses" in net:
            for addr in net["addresses"]:
                if (
                    addr["family"] == "inet"
                    and addr["address"].startswith("192.168.5.")
                ):
                    ip_address = addr["address"]
                    break
        if ip_address:
            break

    if not ip_address:
        print(f"No usable IP found for {name}", file=sys.stderr)
        continue

    host_entry = {
        "ansible_host": ip_address,
        "ansible_user": "mlsysops",
        "ansible_ssh_private_key_file": "/home/mlsysops/.ssh/id_rsa",
        "ansible_python_interpreter": "/usr/bin/python3",
        "k3s_cluster_name": "management" if name == "sysops04" else "sysops01",
        "labels": {
            "is_vm": True,
            "mlsysops.eu/continuumLayer": (
                "continuum" if name == "sysops04" else
                "cluster" if name == "sysops01" else
                "node"
            ),
            "vaccel": "false",
        },
    }

    # Add pod/service CIDRs if needed
    if name == "sysops04":
        host_entry["pod_cidr"] = "10.10.0.0/16"
        host_entry["service_cidr"] = "10.11.0.0/16"
    elif name == "sysops01":
        host_entry["pod_cidr"] = "10.12.0.0/16"
        host_entry["service_cidr"] = "10.13.0.0/16"

    final_group[name] = host_entry

# 5. Write inventory to file
with open("inv.yml", "w") as f:
    yaml.dump(inventory, f, sort_keys=False)

print("Inventory written to inv.yml")

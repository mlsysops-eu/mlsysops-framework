This document acts as a quickstart guide to showcase indicative features of the
`MLSysOps framework`. Please refer to the [installation guide](../installation)
for more detailed installation instructions, or the
[design](../design#architecture) document for more details regarding
`MLSysOps`'s architecture.


## Using Docker

The easiest and fastest way to try out the `MLSysOps framework` would be with
`docker` Before doing so, please make sure that the host system satisfies the
following dependencies:

- [Docker](https://docs.docker.com/engine/install/ubuntu/)
- [Qemu](https://www.qemu.org/)

### Install Docker

At first we need [docker](https://docs.docker.com/engine/install/ubuntu/).

```bash
$ curl -fsSL https://get.docker.com -o get-docker.sh
$ sudo sh get-docker.sh
$ rm get-docker.sh
$ sudo groupadd docker # The group might already exist
$ sudo usermod -aG docker $USER
```

> Note: Please logout and log back in from the shell, in order to be able to use
> docker without sudo

#### Install Qemu

Let's make sure that [Qemu](https://www.qemu.org/download/) is installed:

```bash
$ sudo apt install -y qemu-system
```

## Using containerd and nerdctl

### Install a high-level container runtime

First step is to install [containerd](https://github.com/containerd/containerd) and
setup basic functionality (the `CNI` plugins and a snapshotter).

If a tool is already installed, skip to the next step.

#### Install and configure containerd

We will install [containerd](https://github.com/containerd/containerd) from the
package manager:

```bash
$ sudo apt install containerd
```

In this way we will also install `runc`, but not the necessary CNI plugins.
However, before proceeding to CNI plugins, we will generate the default
configuration for [containerd](https://github.com/containerd/containerd).

```bash
$ sudo mkdir -p /etc/containerd/
$ sudo mv /etc/containerd/config.toml /etc/containerd/config.toml.bak # There might be no configuration
$ sudo containerd config default | sudo tee /etc/containerd/config.toml
$ sudo systemctl restart containerd
```

#### Install CNI plugins

```bash
$ CNI_VERSION=$(curl -L -s -o /dev/null -w '%{url_effective}' "https://github.com/containernetworking/plugins/releases/latest" | grep -oP "v\d+\.\d+\.\d+" | sed 's/v//')
$ wget -q https://github.com/containernetworking/plugins/releases/download/v$CNI_VERSION/cni-plugins-linux-$(dpkg --print-architecture)-v$CNI_VERSION.tgz
$ sudo mkdir -p /opt/cni/bin
$ sudo tar Cxzvf /opt/cni/bin cni-plugins-linux-$(dpkg --print-architecture)-v$CNI_VERSION.tgz
$ rm -f cni-plugins-linux-$(dpkg --print-architecture)-v$CNI_VERSION.tgz
```

#### Setup thinpool devmapper

In order to make use of directly passing the container's snapshot as block
device in the container, we will need to setup the devmapper snapshotter. We can
do that by first creating a thinpool, using the respective
[scripts in `urunc`'s repo](https://github.com/nubificus/urunc/tree/main/script)

```bash
$ wget -q https://raw.githubusercontent.com/nubificus/urunc/refs/heads/main/script/dm_create.sh
$ wget -q https://raw.githubusercontent.com/nubificus/urunc/refs/heads/main/script/dm_reload.sh
$ sudo mkdir -p /usr/local/bin/scripts
$ sudo mv dm_create.sh /usr/local/bin/scripts/dm_create.sh
$ sudo mv dm_reload.sh /usr/local/bin/scripts/dm_reload.sh
$ sudo chmod 755 /usr/local/bin/scripts/dm_create.sh
$ sudo chmod 755 /usr/local/bin/scripts/dm_reload.sh
$ sudo /usr/local/bin/scripts/dm_create.sh
```

> Note: The above instructions will create the thinpool, but in case of reboot,
> you will need to reload it running the `dm_reload.sh` script. Otherwise
> check the [installation guide for creating a service](../installation#create-a-service-for-thinpool-reloading). 

At last, we need to modify
[containerd](https://github.com/containerd/containerd/tree/main) configuration
for the new demapper snapshotter:

- In containerd v2.x:

```bash
$ sudo sed -i "/\[plugins\.'io\.containerd\.snapshotter\.v1\.devmapper'\]/,/^$/d" /etc/containerd/config.toml
$ sudo tee -a /etc/containerd/config.toml > /dev/null <<'EOT'

# Customizations for devmapper

[plugins.'io.containerd.snapshotter.v1.devmapper']
  pool_name = "containerd-pool"
  root_path = "/var/lib/containerd/io.containerd.snapshotter.v1.devmapper"
  base_image_size = "10GB"
  discard_blocks = true
  fs_type = "ext2"
EOT
$ sudo systemctl restart containerd
```

- In containerd v1.x:

```bash
$ sudo sed -i '/\[plugins\."io\.containerd\.snapshotter\.v1\.devmapper"\]/,/^$/d' /etc/containerd/config.toml
$ sudo tee -a /etc/containerd/config.toml > /dev/null <<'EOT'

# Customizations for devmapper

[plugins."io.containerd.snapshotter.v1.devmapper"]
  pool_name = "containerd-pool"
  root_path = "/var/lib/containerd/io.containerd.snapshotter.v1.devmapper"
  base_image_size = "10GB"
  discard_blocks = true
  fs_type = "ext2"
EOT
$ sudo systemctl restart containerd
```

Let's verify that the new snapshotter is properly configured:

```bash
$ sudo ctr plugin ls | grep devmapper
io.containerd.snapshotter.v1           devmapper                linux/amd64    ok
```

### Install nerdctl

After installing [containerd](https://github.com/containerd/containerd) a nifty tool like [nerdctl](https://github.com/containerd/nerdctl/) is useful to get a realistic experience.

```bash
$ NERDCTL_VERSION=$(curl -L -s -o /dev/null -w '%{url_effective}' "https://github.com/containerd/nerdctl/releases/latest" | grep -oP "v\d+\.\d+\.\d+" | sed 's/v//')
$ wget -q https://github.com/containerd/nerdctl/releases/download/v$NERDCTL_VERSION/nerdctl-$NERDCTL_VERSION-linux-$(dpkg --print-architecture).tar.gz
$ sudo tar Cxzvf /usr/local/bin nerdctl-$NERDCTL_VERSION-linux-$(dpkg --print-architecture).tar.gz
$ rm -f nerdctl-$NERDCTL_VERSION-linux-$(dpkg --print-architecture).tar.gz
```

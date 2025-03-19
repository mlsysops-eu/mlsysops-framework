This document guides you through the installation of the `MLSysOps framework`
and all required components for executing all supported scenarios.

We assume a vanilla ubuntu 22.04 environment, although the `MLSysOps framework`
is able to run on a number of distros.

We will be installing and setting up:

- git, wget, bc, make, build-essential
- [runc](https://github.com/opencontainers/runc)
- [containerd](https://github.com/containerd/containerd/)
- [nerdctl](https://github.com/containerd/nerdctl)
- [devmapper](https://docs.docker.com/storage/storagedriver/device-mapper-driver/)
- [Go 1.24.1](https://go.dev/doc/install)
- [qemu](https://www.qemu.org/)
- [firecracker](https://github.com/firecracker-microvm/firecracker)
- [k3s](https://k3s.sh)
- [karmada](https://karmada.io)

Let's go.

> Note: Be aware that some instructions might override existing tools and services.

## Install required dependencies

The following packages are required to complete the installation. Depending
on your specific needs, some of them may not be necessary in your use case.


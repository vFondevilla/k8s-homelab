# Rook Ceph

Rook Ceph provides block storage and object storage for the management cluster.

This component is not active. The management cluster has no Rook namespace, Application, or Ceph custom resources.

## Structure

The `base/` directory contains the namespace and Ceph resources.

The `overlays/management/` directory installs Rook chart `v1.20.2` and includes the base.

The Argo Application is staged in `k8s/argocd/applications/management/rook-ceph.yaml`.
The management Argo root does not include this Application.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/rook-ceph/overlays/management
```

## Erase a Ceph disk

CAUTION: These commands erase all data and partition metadata on `/dev/nvme1n1`.

Start a privileged Ceph shell on the selected node:

```sh
k debug node/node09 -it --image=quay.io/ceph/ceph:v20.2.2 --profile=sysadmin -n rook-ceph -- bash
```

Make sure that `/dev/nvme1n1` is the correct disk. Then operate these commands inside the shell:

```sh
wipefs --all --force /dev/nvme1n1
sgdisk --zap-all /dev/nvme1n1
```

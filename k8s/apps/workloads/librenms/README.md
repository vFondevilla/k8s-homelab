# LibreNMS

LibreNMS provides network monitoring through the official Helm chart.

This component is not active in Argo CD. The management cluster has no LibreNMS namespace or Helm release.

## Structure

The `base/` directory contains the namespace.

The `overlays/management/` directory installs chart `8.2.2` in the `librenms` namespace.

The chart includes the web frontend, pollers, RRDCached, Redis, and MySQL.

## Storage

The values use the `nfs-client` StorageClass for RRDCached, Redis, and MySQL.

Back up the persistent volumes and generated Secrets before you restore or move a live release.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/workloads/librenms/overlays/management
```

The staged Application is outside the active Argo root.

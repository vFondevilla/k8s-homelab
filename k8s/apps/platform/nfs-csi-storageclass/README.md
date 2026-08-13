# NFS CSI StorageClass

This component preserves the legacy `nfs-csi` StorageClass definitions.

The component does not install an NFS CSI driver.

The base preserves the current live StorageClass definition. It uses `10.254.0.3` and permits volume expansion.

## Overlays

The management overlay uses the NFS server at `10.1.0.3`.

The tenant overlay uses the NFS server at `10.254.0.3`.

The tenant overlay preserves the legacy definition without volume expansion.

Both overlays use the directory `/mnt/flash/k8s_static_pv`.

Both overlays define `nfs-csi` as a default StorageClass.

## Live-state constraint

The management cluster currently uses `10.254.0.3` in its live `nfs-csi` StorageClass.

The cluster also defines `nfs-client` as a default StorageClass. This duplicate default state already exists.

No `nfs.csi.k8s.io` CSI driver is registered in the management cluster.

A Bound Prometheus volume uses `nfs-csi` as its StorageClass name. Its persistent volume has a static NFS source.

Do not add this component to Argo discovery until you select the correct management server address.

Do not remove or replace the live StorageClass during this review.

## Render

Operate these commands from the repository root:

```sh
kustomize build k8s/apps/platform/nfs-csi-storageclass/overlays/management
kustomize build k8s/apps/platform/nfs-csi-storageclass/overlays/tenant
```

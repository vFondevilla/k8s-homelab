# NFS Subdirectory Provisioner

The NFS Subdirectory Provisioner creates dynamic NFS volumes for the management cluster.

This component is a platform storage component.

## Overlays

The management overlay is `overlays/management/`.

The overlay creates resources in the `nfs-subdir` namespace. It also creates the cluster-wide `nfs-client` StorageClass.

The tenant overlay is `overlays/tenant/`.

The management overlay uses `10.1.0.3`. The tenant overlay uses `10.254.0.3`.

## Dependencies

The provisioner uses the NFS server at `10.1.0.3`.

The server directory `/mnt/flash/k8s_static_pv/` must exist and permit provisioner writes.

## Persistent resources

Bound volumes use the `nfs-client` StorageClass. Do not remove the StorageClass or change its provisioner name.

The current provisioner name is `cluster.local/nfs-subdir-external-provisioner`.

Preserve the Application, Deployment, pod, and StorageClass UIDs during a source-path migration.

Also preserve every PV and PVC that uses `nfs-client`.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/nfs-subdir/overlays/management
kustomize build --enable-helm k8s/apps/platform/nfs-subdir/overlays/tenant
```

## Migration constraint

Preserve the `in-cluster-nfs-subdir` Application name.

Synchronize this component without pruning. Then make sure that all `nfs-client` volumes remain Bound.

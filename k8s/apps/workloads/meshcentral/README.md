# MeshCentral

MeshCentral is a user service on the management cluster. It provides remote device management.

This component is a workload component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `meshcentral` namespace.

## Dependencies

The service uses two static NFS volumes. The NFS server is `10.254.0.3`.

These server directories must exist:

- `/mnt/flash/k8s_static_pv/meshcentral/data`
- `/mnt/flash/k8s_static_pv/meshcentral/files`

## Persistent resources

The PVs and PVCs are named `meshcentral-data` and `meshcentral-files`. Both PV reclaim policies are `Retain`.

The PVCs set `volumeName` explicitly. This value prevents a change to an immutable field after binding.

Preserve the PV, PVC, Deployment, and Application UIDs during a source-path migration.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/workloads/meshcentral/overlays/management
```

## Migration constraint

Preserve the `in-cluster-meshcentral` Application name.

Synchronize this component without pruning. Then make sure that both PVs and PVCs remain Bound.

# HWPO Flex

HWPO Flex is a user service on the management cluster. The service stores progress data on NFS.

This component is a workload component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `hwpo-flex` namespace.

## Image

The management overlay uses `zot.apps.fondevilla.io/hwpo-flex:latest`.

Replace the floating tag with an immutable image tag in a separate change.

Do not combine that image change with a source-path migration.

## Dependencies

The ingress uses the Cilium ingress class. It also uses the `letsencrypt-prod` ClusterIssuer.

The persistent volume uses the NFS server at `10.254.0.3`.

The directory `/mnt/flash/k8s_static_pv/hwpo-flex` must exist on that server.

## Persistent resources

The PersistentVolume is `hwpo-flex-progress-pv`. Its reclaim policy is `Retain`.

The PersistentVolumeClaim is `hwpo-flex-progress` in the `hwpo-flex` namespace.

Preserve both resource names and UIDs during a source-path migration.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/workloads/hwpo-flex/overlays/management
```

## Migration constraint

Preserve the `in-cluster-hwpo-flex` Application name during a source-path migration.

Synchronize this component without pruning. Then make sure that the PV and PVC remain Bound.

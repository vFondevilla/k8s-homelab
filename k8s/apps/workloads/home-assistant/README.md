# Home Assistant

Home Assistant is a user service on the management cluster. The service stores its configuration on an NFS volume.

This component is a workload component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `home-assistant` namespace.

## Dependencies

The ingress uses the Cilium ingress class. It also uses the `letsencrypt-prod` ClusterIssuer.

External Secrets Operator gets the application secret from 1Password.

The persistent volume uses the NFS server at `10.1.0.3`.

The directory `/mnt/flash/k8s_static_pv/home-assistant` must exist on that server.

## Persistent resources

The PersistentVolume and PersistentVolumeClaim are both named `nfs-truenas`. The PV reclaim policy is `Retain`.

Preserve both resource names and UIDs during a source-path migration.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/workloads/home-assistant/overlays/management
```

## Migration constraint

Preserve the `in-cluster-home-assistant` Application name during a source-path migration.

Synchronize this component without pruning. Then make sure that the PV and PVC remain Bound.

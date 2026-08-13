# Mosquitto

Mosquitto is an MQTT broker on the management cluster. Home automation services use this broker.

This component is a workload component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `mosquitto` namespace.

## Dependencies

The service uses a static NFS volume. The NFS server is `10.254.0.3`.

The directory `/mnt/flash/k8s_static_pv/mosquitto` must exist on that server.

## Persistent resources

The PV and PVC are named `mosquitto`. The PV reclaim policy is `Retain`.

The PVC sets `volumeName` explicitly. This value prevents a change to an immutable field after binding.

Preserve the PV, PVC, Deployment, and Application UIDs during a source-path migration.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/workloads/mosquitto/overlays/management
```

## Migration constraint

Preserve the `in-cluster-mosquitto` Application name.

Synchronize this component without pruning. Then make sure that the PV and PVC remain Bound.

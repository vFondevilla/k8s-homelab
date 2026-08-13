# Zigbee2MQTT

Zigbee2MQTT connects Zigbee devices to the MQTT broker. It runs on the management cluster.

This component is a workload component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `z2m` namespace.

## Dependencies

The service connects to Mosquitto. It also needs access to its configured Zigbee coordinator.

The service uses a static NFS volume. The NFS server is `10.254.0.3`.

The directory `/mnt/flash/k8s_static_pv/zigbee2mqtt` must exist on that server.

## Persistent resources

The PV is named `zigbee2mqtt`. The StatefulSet claim is `data-volume-zigbee2mqtt-0`.

The PV reclaim policy is `Retain`. The claim template sets `volumeName: zigbee2mqtt`.

Preserve the PV, PVC, StatefulSet, pod, and Application UIDs during a source-path migration.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/workloads/zigbee2mqtt/overlays/management
```

## Migration constraint

Preserve the `in-cluster-zigbee2mqtt` Application name.

Synchronize this component without pruning. Then make sure that the PV and PVC remain Bound.

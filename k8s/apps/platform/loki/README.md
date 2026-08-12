# Loki

Loki stores logs from the management cluster. Alloy and other log clients send data to this service.

This component is a platform observability component.

## Source

The management overlay uses the Grafana Loki Helm chart at version `6.55.0`.

Kustomize gets the chart from `https://grafana.github.io/helm-charts` during the render.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `loki` namespace. It uses a single-binary StatefulSet.

## Dependencies

External Secrets Operator gets the MinIO credentials from 1Password.

The chart uses a persistent volume for Loki storage.

## Persistent resources

The PersistentVolumeClaim is `storage-loki-0` in the `loki` namespace.

Preserve the StatefulSet, pod, PV, and PVC identities during a source-path migration.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/loki/overlays/management
```

## Migration constraint

Preserve the `in-cluster-loki` Application name during a source-path migration.

Synchronize this component without pruning. Then make sure that the PV and PVC remain Bound.

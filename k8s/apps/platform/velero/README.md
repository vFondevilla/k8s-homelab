# Velero

Velero stores Kubernetes backups in the homelab MinIO service.

This component is not active in the management cluster.

## Overlay

The management overlay is `overlays/management/`.

The overlay installs Velero chart `8.3.0` in the `velero` namespace.

The ExternalSecret creates the MinIO credentials from 1Password.

The configuration disables volume snapshots. Persistent volume data needs a separate backup method.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/velero/overlays/management
```

Do not add this component to Argo discovery until the backup and restore procedure is complete.

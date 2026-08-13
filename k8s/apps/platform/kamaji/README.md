# Kamaji

Kamaji provides hosted Kubernetes control planes for tenant clusters.

This component is a platform cluster-lifecycle component.

## Overlay

The management overlay is `overlays/management/`.

The overlay installs the Kamaji controller and an etcd datastore in the `kamaji-system` namespace.

## Dependencies

cert-manager issues the Kamaji webhook certificate.

The etcd StatefulSet uses three claims from the `nfs-client` StorageClass.

The Kamaji CAPI provider is a separate component. The fleet class is also outside this component.

## Persistent resources

Preserve the etcd StatefulSet, pods, PVs, and PVCs during a source-path migration.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/kamaji/overlays/management
```

## Migration constraint

Preserve the `in-cluster-kamaji` Application name.

Synchronize this component without pruning. Then make sure that all three etcd claims remain Bound.

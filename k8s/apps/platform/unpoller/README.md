# Unpoller

Unpoller exports UniFi controller metrics for Prometheus. It runs on the management cluster.

This component is a platform observability component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `unpoller` namespace.

## Dependencies

External Secrets Operator gets the UniFi account password from 1Password.

The PodMonitor requires the Prometheus Operator custom resource definitions.

## Persistent resources

This component has no persistent volume.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/platform/unpoller/overlays/management
```

## Migration constraint

Preserve the `in-cluster-unpoller` Application name during a source-path migration.

Preserve the Deployment, pod, and ExternalSecret identities when the rendered resources do not change.

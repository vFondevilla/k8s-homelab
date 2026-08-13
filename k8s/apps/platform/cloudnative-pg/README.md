# CloudNativePG

CloudNativePG manages PostgreSQL clusters on Kubernetes.

This component is not active in the management cluster.

## Overlay

The management overlay is `overlays/management/`.

The overlay installs chart version `0.29.0` in the `cnpg-system` namespace.

The operator image uses the local Zot registry mirror.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/cloudnative-pg/overlays/management
```

Do not add this component to Argo discovery until a workload needs the operator.

# Cluster API

This component installs Cluster API, the kubeadm providers, and the KubeVirt infrastructure provider.

This component is a platform cluster-lifecycle component.

## Overlay

The management overlay is `overlays/management/`.

The component installs four controller Deployments and their required CRDs, webhooks, permissions, and certificates.

## Separate components

The Kamaji CAPI provider is a separate component. The Kamaji and KubeVirt fleet class is also separate.

Apply fleet classes and claims only after all provider controllers are Ready.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/platform/cluster-api/overlays/management
```

## Migration constraint

Preserve the `in-cluster-cluster-api` Application name.

The normalized path must render the same 70 resources during the path migration.

Enable the `ClusterResourceSet` feature in a separate change after the path migration.

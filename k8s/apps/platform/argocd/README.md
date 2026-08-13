# Argo CD

Argo CD reconciles the management cluster from this Git repository.

This component installs Argo CD. It does not define the root Application or the central ApplicationSet.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates Argo CD resources in the `argocd` namespace. It also creates required cluster-wide permissions.

## Dependencies

External Secrets Operator gets the Google OAuth secret from 1Password.

The encrypted repository configuration needs the repository age key. Do not commit a decrypted repository secret.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/platform/argocd/overlays/management
```

## Migration constraint

Preserve the `in-cluster-argocd` Application name.

Keep automated sync disabled during the source-path migration. Synchronize only after you review all cluster-wide permission changes.

The root Application remains `argocd`. Its source is `k8s/argocd`, not this component path.

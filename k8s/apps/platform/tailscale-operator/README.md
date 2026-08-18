# Tailscale Kubernetes Operator

The management overlay installs Tailscale Kubernetes Operator chart version
`1.102.2` in the `tailscale` namespace. The chart reads its OAuth credentials
from the pre-created `operator-oauth` Secret. No OAuth value is stored in Git.

The External Secrets Operator creates that Secret from the 1Password Login item
named `Tailscale Oauth K8s Operator` in the `lab` vault:

- `username` becomes `client_id`.
- `password` becomes `client_secret`.

This mapping requires a Login item with the standard `username` and `password`
fields. If the item uses custom field labels, change the `property` values in
`base/external-secret.yaml`.

The OAuth client must have write access to **Devices Core**, **Auth Keys**, and
**Services**, and it must be tagged `tag:k8s-operator`. The tailnet policy must
allow `tag:k8s-operator` to own the proxy tag `tag:k8s`.

The operator's Kubernetes API server proxy is disabled. The operator installs
the `tailscale` IngressClass and tags its managed proxies with `tag:k8s`.

## Render

Run this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/tailscale-operator/overlays/management
```

After Argo CD syncs the application, verify the credentials and operator:

```sh
kubectl -n tailscale get externalsecret operator-oauth
kubectl -n tailscale rollout status deployment/operator
kubectl -n tailscale logs deployment/operator
```

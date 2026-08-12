# Platform components

Reusable controllers and cluster capabilities belong under this directory.
Each component should expose a singular `base/` and role-oriented overlays,
such as `overlays/management/` and `overlays/tenant/`.

Argo CD `Application` wrappers do not belong in component directories; they
belong under `k8s/argocd/`.

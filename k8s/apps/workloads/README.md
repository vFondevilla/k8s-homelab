# Workload components

User services belong under this directory.

Each component uses one `base/` and one or more role overlays.

The standard roles are `management`, `tenant`, and `vps`.

Argo CD `Application` wrappers remain under `k8s/argocd/`.

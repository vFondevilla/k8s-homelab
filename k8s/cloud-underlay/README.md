# Cloud-underlay migration

Git tracks no deployable Kubernetes resources in this directory.

This directory contains migration documents only. Do not use it as an Argo source or a component root.

## Tracked files

- `README.md` describes the directory status.
- `DEMOCRATIC_CSI_PLAN.md` records the storage migration design.

## Normalized ownership

The reorganization moved the tracked resources to these locations:

| Resource type | Location |
| --- | --- |
| Argo resources | `k8s/argocd/` |
| Cluster controllers and shared capabilities | `k8s/apps/platform/` |
| User services, including Zot | `k8s/apps/workloads/` |

Local untracked files can still exist in this directory. Treat those files as user work until you review their ownership.

Before you add a local resource to Git, move it to the applicable normalized directory.

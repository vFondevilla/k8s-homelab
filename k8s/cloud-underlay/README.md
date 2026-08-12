# Cloud-underlay ownership

This directory is a transitional compatibility surface for resources that
bootstrap or support the existing management cluster. It is not a second Argo
orchestration root and should not receive new application wrappers.

The eventual ownership split is:

| Current area | Target ownership | Reason |
| --- | --- | --- |
| `argocd.yaml`, `cert-manager.yaml`, `cilium.yaml`, `external-secrets-operator.yaml`, `onepassword-connect.yaml`, `prometheus-crd.yaml` | `k8s/argocd/` plus `k8s/apps/platform/` | Management-cluster orchestration and platform components are already being staged there. |
| `democratic-csi/`, `rook/`, `storageclasses/` | `k8s/apps/platform/` | Storage provisioners and storage classes are management platform capabilities. |
| `tinkerbell/` | `k8s/apps/platform/tinkerbell/` | Machine provisioning is a platform capability; examples remain opt-in and outside automatic discovery. |
| `cnpg/` | `k8s/apps/platform/` | The CloudNativePG controller is a platform dependency when enabled. |
| `librenms/`, `zot/` | `k8s/apps/workloads/` | These are user-facing services, not cluster bootstrap capabilities. |
| `DEMOCRATIC_CSI_PLAN.md` | Documentation near the migrated storage component | It records storage design and acceptance work, not an Argo resource. |

Until each source has been copied, rendered, compared, and switched, the
legacy files remain in place for rollback. The root Kustomization here is
therefore retained only for the existing bootstrap flow and must not be added
to the new `k8s/argocd/` root.


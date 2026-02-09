# kube-v2

ApplicationSet manifests for the v2 layout:
- Base apps deployed to all clusters
- Per-cluster apps deployed based on overlay presence
- Application names follow $CLUSTER-$APP

Assumptions
- Each Argo CD cluster secret has label `cluster=<name>` (e.g., control-plane, workload, vps).
- App repo layout: `k8s/apps/<app>/base` and `k8s/apps/<app>/overlays/<cluster>`.
- Update `repoURL` if your repository changes.

How to use
- Point an Argo CD Application at `k8s/kube-v2/applicationSets/` (or `k8s/kube-v2` if you add a kustomization here).
- Ensure overlays exist for each base app in each cluster.
- Add or remove overlays under `apps/<app>/overlays/<cluster>` to control per-cluster deployments.


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

## Disabling sync or auto-healing for individual apps

All ApplicationSets set `ignoreApplicationDifferences` on `/spec/syncPolicy`, so any manual change to an app's sync policy is preserved and will not be reverted by the ApplicationSet controller.

Application names follow the pattern `<cluster>-<app>` (e.g., `control-plane-cilium`, `workload-loki`).

### Disable automated sync entirely

```sh
argocd app set <cluster>-<app> --sync-policy none
```

The app will no longer sync automatically. You can still trigger a manual sync from the UI or CLI.

### Disable self-healing only (keep auto-sync)

```sh
kubectl patch application <cluster>-<app> -n argocd \
  --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":false,"prune":true}}}}'
```

ArgoCD will still sync on new commits but will not revert out-of-band changes to live resources.

### Disable pruning only

```sh
kubectl patch application <cluster>-<app> -n argocd \
  --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":true,"prune":false}}}}'
```

ArgoCD will not delete resources removed from git, but will still apply additions and updates.

### Re-enable full automation

```sh
kubectl patch application <cluster>-<app> -n argocd \
  --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":true,"prune":true}}}}'
```

This restores the default behaviour defined in the ApplicationSet template.


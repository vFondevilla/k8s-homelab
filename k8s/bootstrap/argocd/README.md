# Argo CD bootstrap

This directory contains only the manually applied resources that establish
Argo CD GitOps management for the management cluster.

The bootstrap root points at `k8s/argocd/` after the orchestration tree has been
rendered and compared with the live Argo inventory. Normal component manifests
do not belong here.

The first activation is manual and non-pruning. During the Phase 2 transition,
the root first owned only the protected `apps-control-plane` ApplicationSet.
The `github-arc-vfondevilla` ApplicationSet was later added to the same root.
Both are synced from `k8s/argocd/` on each manual root sync. Additional
management and tenant orchestration is added incrementally after reviewed live
diffs.

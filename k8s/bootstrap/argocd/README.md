# Argo CD bootstrap

This directory contains only the manually applied resources that establish
Argo CD GitOps management for the management cluster.

The bootstrap root points at `k8s/argocd/` after the orchestration tree has been
rendered and compared with the live Argo inventory. Normal component manifests
do not belong here.

The first activation is manual and non-pruning. During the Phase 2 transition,
the root owns only the protected `apps-control-plane` ApplicationSet; additional
management and tenant orchestration is added incrementally after reviewed live
diffs.

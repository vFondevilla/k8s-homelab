# Cluster API

Installs Cluster API with the kubeadm bootstrap/control-plane providers and the
KubeVirt infrastructure provider.

Pinned versions:

- Cluster API: `v1.13.2`
- Cluster API Provider KubeVirt: `v0.11.2`

Prerequisites:

- `cert-manager` is installed before these controllers reconcile.
- KubeVirt and CDI are installed on the management cluster.

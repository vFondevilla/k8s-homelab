# Cluster API examples

These examples are reference manifests. Argo CD does not discover this directory.

The `ubuntu-2404-kubevirt/` example uses a Kubeadm control plane and KubeVirt machines.

The `kubeadm-kubevirt/` example contains a smaller CAPK cluster and an optional Cilium HelmChartProxy.

The examples can use old API versions. Compare them with the installed providers before you apply them.

Do not store generated kubeconfigs, bootstrap Secrets, or private keys in this directory.

# Kubeadm KubeVirt example

This example creates a Kubeadm cluster with KubeVirt control-plane and worker machines.

The optional `helmchartproxy-cilium.yaml` requires the Cluster API Add-on Provider for Helm.

The management cluster does not contain that provider. Do not apply the HelmChartProxy until you install the required CRD.

The manifests are not part of an Argo Kustomization.

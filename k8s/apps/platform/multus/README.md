# Multus

Multus provides additional network interfaces for Kubernetes pods.

Cilium remains the primary CNI. Use Multus only in an explicit Cilium chain.

## Overlays

The management overlay is `overlays/management/`.

The tenant overlay is `overlays/tenant/`.

Both overlays use Multus `v4.2.3` and the thick daemonset.

The patch gives the Multus container explicit resource requests and limits.

## Live-state constraint

The management cluster contains a manually installed `kube-multus-ds` DaemonSet.

No live Argo Application owns Multus. This path move does not change the live DaemonSet.

Do not add Multus to Argo discovery until you compare the normalized render with the live resources.

## Render

Operate these commands from the repository root:

```sh
kustomize build k8s/apps/platform/multus/overlays/management
kustomize build k8s/apps/platform/multus/overlays/tenant
```

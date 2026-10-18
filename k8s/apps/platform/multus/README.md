# Multus

Multus provides additional network interfaces for Kubernetes pods.

Cilium remains the primary CNI. Multus delegates the default network to Cilium and provides optional additional interfaces.

## Overlays

The management overlay is `overlays/management/`.

The tenant overlay is `overlays/tenant/`.

Both overlays use Multus `v4.2.3` and the thick daemonset.

The patch gives the Multus container explicit resource requests and limits.

## Management configuration

The `in-cluster-multus` Argo CD Application manages the management overlay.

The daemon configuration selects `05-cilium.conflist` through `multusMasterCNI`.
This explicit selection prevents an earlier CNI filename from replacing Cilium as the default network.

An init container moves retired Kube-OVN CNI files into `/etc/cni/retired-kube-ovn` on each node.
The directory is outside the active CNI configuration directory.
The init container also covers nodes that return after an outage.

Cilium uses `cni.exclusive: false` so that its configuration can coexist with the Multus configuration.
Kube-OVN is no longer installed in the management cluster.

## Render

Operate these commands from the repository root:

```sh
kustomize build k8s/apps/platform/multus/overlays/management
kustomize build k8s/apps/platform/multus/overlays/tenant
```

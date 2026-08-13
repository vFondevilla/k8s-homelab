# Zot

Zot provides the container registry for the management cluster.

Helm currently owns the live Zot release. Before you activate the staged Argo Application, review the resource ownership.

## Storage identity

The base keeps these live storage identifiers:

- PersistentVolume: `zot-static-pv`
- PersistentVolumeClaim: `zot-pvc-zot-0`
- NFS server: `10.1.0.3`
- StorageClass: `nfs-client`
- Capacity: `100Gi`

The PersistentVolume uses the `Retain` policy. The resource-policy annotations keep both storage resources during a Helm removal.

## Structure

The `base/` directory contains the namespace and static storage resources.

The `overlays/management/` directory installs Zot chart `0.1.121` and uses the existing claim.

The Argo Application is staged in `k8s/argocd/applications/management/zot.yaml`.
The management Argo root does not include this Application.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/zot/overlays/management
```

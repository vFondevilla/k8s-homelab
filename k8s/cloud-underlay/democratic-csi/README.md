# democratic-csi

Pinned democratic-csi deployments for TrueNAS SCALE 25.04.2.6.

- Helm chart: `0.15.1`
- Driver image: `v1.9.5`
- Management API: `https://10.1.0.4:4443`
- NFS and iSCSI data endpoint: `10.254.0.4`
- iSCSI portal group: `1`
- iSCSI initiator group: `1`

The control-plane and workload overlays use distinct CSI driver identities,
instance IDs, parent datasets, and iSCSI target prefixes. Neither StorageClass
is configured as default. Snapshot sidecars and classes are disabled until the
snapshot CRDs and controller are installed.

The TrueNAS certificate is currently expired. `allowInsecure: true` is an
explicit homelab exception accepted by the operator.

Talos `v1.11.0` with `iscsi-tools v0.2.0` uses
`/usr/local/sbin/iscsiadm`, but no longer exposes `/usr/local/etc/iscsi` to
kubelet. Configure the chart's writable iSCSI directory as `/var/iscsi` with
hostPath type `DirectoryOrCreate`. The host-side `iscsiadm` process continues
to use the Talos-managed initiator configuration.

Render an overlay with:

```sh
kustomize build --enable-helm democratic-csi/overlays/control-plane
kustomize build --enable-helm democratic-csi/overlays/workload
```

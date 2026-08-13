# Democratic CSI

This component contains pinned Democratic CSI configurations for TrueNAS SCALE.

- Helm chart: `0.15.1`
- Driver image: `v1.9.5`
- Management API: `https://10.1.0.3:443`
- NFS and iSCSI data endpoint: `10.254.0.3`
- iSCSI portal group: `1`
- iSCSI initiator group: `1`

The management and tenant overlays use different CSI driver identities.

They also use different instance IDs, parent datasets, and iSCSI target prefixes.

Neither StorageClass is the default StorageClass.

Snapshot sidecars and classes remain disabled until the cluster contains the snapshot controller and CRDs.

The TrueNAS certificate is expired. The configuration uses `allowInsecure: true` as an explicit homelab exception.

Talos `v1.11.0` with `iscsi-tools v0.2.0` uses `/usr/local/sbin/iscsiadm`.

Talos does not expose `/usr/local/etc/iscsi` to kubelet.

The chart uses `/var/iscsi` as its writable iSCSI directory. Its hostPath type is `DirectoryOrCreate`.

Render an overlay with:

```sh
kustomize build --enable-helm k8s/apps/platform/democratic-csi/overlays/management
kustomize build --enable-helm k8s/apps/platform/democratic-csi/overlays/tenant
```

This component is not active. Do not add it to Argo discovery before storage validation is complete.

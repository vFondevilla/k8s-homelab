# democratic-csi with TrueNAS SCALE and Talos Linux

## Goal

Introduce `democratic-csi` as a dynamic storage provisioner for the Kubernetes
clusters, backed by TrueNAS SCALE, without disrupting the existing NFS storage
classes or persistent volumes.

The known TrueNAS endpoints are:

- `10.1.0.4` from the control-plane network.
- `10.254.0.4` from the workload-cluster network.

The confirmed TrueNAS release is **SCALE 25.04.2.6 (Fangtooth)**.

The confirmed cluster versions and scope are:

- Talos Linux `v1.11.0`
- Kubernetes `v1.32.0`
- Target clusters: control-plane and workload
- Protocols: NFSv4.1 and iSCSI
- Storage network: `10.254.0.0/24`
- TrueNAS storage endpoint: `10.254.0.4`
- TrueNAS management endpoint: `https://10.1.0.4:4443`

The existing static NFS dataset is `SSD/k8s_static_pv`. New CSI-managed volumes
will live below `SSD/democratic-csi` and must not be mixed with the existing
static volumes.

## Proposed architecture

Deploy NFS first and validate it, then deploy the required iSCSI service as a
separate release.

### NFS deployment

- Helm release: `truenas-nfs`
- CSI driver name: `org.democratic-csi.truenas-nfs`
- StorageClass: `truenas-nfs`
- Protocol: NFSv4.1
- Initial reclaim policy: `Retain`
- Initial default status: not default
- Access modes: primarily `ReadWriteMany` and `ReadWriteOnce`
- Snapshot support: enabled after installing or confirming a cluster snapshot
  controller

Use a unique parent dataset for each Kubernetes cluster:

```text
SSD/democratic-csi/control-plane/nfs
SSD/democratic-csi/workload/nfs
```

Each cluster must also use a unique CSI driver name if both clusters deploy an
independent democratic-csi controller. For example:

```text
org.democratic-csi.control-plane.nfs
org.democratic-csi.workload.nfs
```

### iSCSI deployment

- Helm release: `truenas-iscsi`
- StorageClass: `truenas-iscsi`
- Intended access mode: `ReadWriteOnce`
- Intended workloads: databases, VM disks, and latency-sensitive applications
- Initial reclaim policy: `Retain`
- Initial default status: not default

Use separate zvol roots per cluster:

```text
SSD/democratic-csi/control-plane/iscsi
SSD/democratic-csi/workload/iscsi
```

NFS and iSCSI must be installed as separate Helm releases with unique release
names, CSI driver names, StorageClasses, parent datasets, and asset-name
prefixes.

## Phase 0: Compatibility gate

Do not create datasets or deploy the driver until the remaining versions have
been recorded:

- [x] TrueNAS SCALE version on `10.1.0.4`: `25.04.2.6`
- [x] Talos Linux version: `v1.11.0`
- [x] Kubernetes version: `v1.32.0`
- [x] Selected democratic-csi image version: `v1.9.5`
- [x] Selected democratic-csi chart version: `0.15.1`

The chart and image selections were verified against the upstream chart index
and Git tags on 2026-07-12. The chart defaults to the mutable `latest` driver
tag, so both controller and node driver image tags must be overridden with
`v1.9.5`. Selection is not proof of TrueNAS 25.04 compatibility; the disposable
compatibility tests below remain mandatory.

### Verified TrueNAS inventory (2026-07-12)

Read-only discovery through the TrueNAS REST API established the following:

- SCALE reports version `25.04.2.6` and hostname `truenas`.
- The deprecated REST API is currently reachable and accepts a newly provided
  API key at `https://10.1.0.4:4443/api/v2.0/`.
- The supported management API for future TrueNAS releases is still the
  versioned JSON-RPC WebSocket API; REST availability on this release does not
  make a future TrueNAS 26 upgrade safe.
- Pool `SSD` is online and healthy, uses `lz4`, and is about 498 GB raw.
- `SSD` is a **single-disk pool** (`sdd1`) with no mirror, RAIDZ, spare, cache,
  or special vdev. A disk failure will lose the pool.
- The pool API reports about 309 GB free, while the root dataset reports about
  162 GiB available. Capacity planning must use the allocatable value observed
  by ZFS/datasets and leave operational headroom.
- Pool fragmentation is 47% and autotrim is off.
- `SSD/democratic-csi` does not exist yet.
- Existing static storage includes both `SSD/k8s_static_pv` and
  `SSD/k8s_static_volumes`; neither is to be managed by democratic-csi.
- NFS is enabled and running. Existing exports already permit
  `10.254.0.0/24`, proving that network is used for storage today.
- NFS is not restricted to specific bind addresses (`bindip` is empty).
- iSCSI is disabled and stopped.
- No iSCSI portals, initiator groups, targets, or extents exist.
- TrueNAS interfaces `10.1.0.4/24` and `10.254.0.4/24` are up with MTU 9000.
- TrueNAS has a default gateway through `10.1.0.1` and no static routes.
- The default TrueNAS management certificate is expired.
- An unrelated critical SMB ACL/path alert also exists under
  `main_pool/data/work/revolut-folder`; it is outside this project but should be
  resolved separately.

The API key named `truenas codex api key` was provided for discovery. It must
not be reused as the runtime democratic-csi credential. Create a separate,
rotatable service identity and key for the deployed driver.

TrueNAS deprecated its REST API in 25.04 and removes it in TrueNAS 26 in favor
of a versioned JSON-RPC WebSocket API. The `freenas-api-*` democratic-csi
drivers are documented as experimental and historically depend on the legacy
API. The traditional TrueNAS drivers can also use the TrueNAS API for share or
target management.

The installed release is in the transitional category: SCALE 25.04.2.6 still
has the deprecated REST API, but its supported API generation is JSON-RPC 2.0
over WebSocket. No explicit upstream democratic-csi statement confirming
25.04.2.6 compatibility was found. Therefore, compatibility must be proven with
the exact pinned chart and image versions before production use.

Use the following decision gate:

- TrueNAS 24.10 or earlier: proceed with an API or SSH-based driver after a
  normal staging test.
- TrueNAS 25.04 or 25.10: prove compatibility with the exact democratic-csi
  version using disposable datasets and claims.
- TrueNAS 26 or later: do not proceed unless the selected democratic-csi
  version explicitly supports the current TrueNAS WebSocket API.

Do not upgrade TrueNAS across this compatibility boundary while CSI-managed
volumes are in production without testing the upgrade first.

For the current `25.04.2.6` installation:

- [x] Confirm that `/api/v2.0/` is enabled at the management endpoint and accepts
  authenticated read-only requests.
- [ ] Confirm that `/api/v2.0/` is reachable from each cluster's CSI controller
  network.
- [ ] Use a new user-linked API key created in the TrueNAS UI rather than a
  migrated legacy key.
- [x] Test API authentication without committing or printing the key. On
  2026-07-12, the dedicated token authenticated successfully to
  `/api/v2.0/system/info` with `Authorization: Bearer`; `X-API-KEY` returned
  HTTP 401 on SCALE 25.04.2.6.
- [ ] Pin TrueNAS at `25.04.2.6` during the CSI evaluation.
- [ ] Do not upgrade to TrueNAS 26 while democratic-csi depends on REST calls.
- [ ] Enable democratic-csi debug logging only during the disposable test and
  verify that logs redact credentials before retaining them.
- [ ] Prove dataset creation, NFS share creation, snapshot/clone operations, and
  cleanup through the chosen driver.
- [ ] If testing iSCSI, separately prove portal/target/extent creation and
  deletion; NFS success does not establish iSCSI compatibility.

If any operation fails because of a missing or changed REST endpoint, stop the
evaluation. Do not compensate with partially manual creation of CSI-owned
shares, targets, extents, datasets, or zvols. Either select a democratic-csi
release that explicitly supports the API, keep TrueNAS on a confirmed supported
release, or reassess the CSI driver choice.

## Phase 1: Network validation

Confirm connectivity from every schedulable Kubernetes node, not only from an
administrator workstation.

- [ ] Reach TrueNAS at `10.254.0.4` from every schedulable node in both
  clusters. Verified from all three nodes in the currently reachable cluster;
  the other target cluster remains pending.
- [ ] Confirm the control-plane cluster has an explicit route to
  `10.254.0.0/24` and a working return route.
- [ ] Confirm the workload cluster uses `10.254.0.0/24` for its storage data
  path.
- [ ] Confirm CSI configuration never uses the management address `10.1.0.4`
  as an NFS or iSCSI data endpoint.
- [ ] Reach NFS on `10.254.0.4:2049/TCP`.
- [ ] Reach TrueNAS HTTPS/API at `10.1.0.4:4443` from CSI controller pods.
- [ ] Reach SSH on TCP 22 if using an SSH-based driver.
- [ ] Reach iSCSI on `10.254.0.4:3260/TCP` from both clusters. Verified from
  `node07`, `node08`, and `node09` using source addresses `10.254.0.17`,
  `10.254.0.18`, and `10.254.0.19`, respectively.
- [ ] Confirm TrueNAS has return routes to every Kubernetes node source address.
- [ ] Confirm firewall rules restrict storage services to Kubernetes nodes.
- [ ] Confirm MTU is consistent across the complete storage path.

The controller will use `https://10.1.0.4:4443` for management, while all
provisioned NFS shares and iSCSI portals must advertise `10.254.0.4`.

Both TrueNAS interfaces use MTU 9000. Do not assume the Kubernetes nodes and
intermediate network match: validate large, non-fragmented packets end-to-end.
If any part of either cluster path is MTU 1500, standardize the entire path or
use MTU 1500 for storage before acceptance testing.

Use standard MTU initially. Enable jumbo frames only after verifying them
end-to-end on every node, switch, VLAN, and TrueNAS interface in the path.

## Phase 2: TrueNAS preparation

### Datasets

- [x] Accept the single-disk pool without ZFS redundancy for this homelab
  deployment. The operator explicitly accepted the data-loss failure domain on
  2026-07-12.
- [ ] Establish an independent, restore-tested backup target outside `SSD`.
- [ ] Set a conservative CSI capacity budget based on dataset availability, not
  raw pool size; reserve at least 20% free space for ZFS operation.
- [ ] Review the pool's 47% fragmentation and whether autotrim should be enabled
  for the underlying SSD before adding dynamic workloads.
- [x] Create `SSD/democratic-csi` as the CSI root dataset.
- [x] Create `SSD/democratic-csi/control-plane/nfs`.
- [x] Create `SSD/democratic-csi/control-plane/iscsi`.
- [x] Create `SSD/democratic-csi/workload/nfs`.
- [x] Create `SSD/democratic-csi/workload/iscsi`.
- [x] Enable or inherit ZFS compression, preferably `lz4`. The created CSI
  hierarchy reports `LZ4` compression.
- [x] Do not set CSI dataset quotas; allow CSI to use the pool's available
  capacity. Continue to reserve operational ZFS headroom through monitoring and
  admission/usage practices rather than a dataset quota.
- [ ] Keep TrueNAS snapshot and replication policies separate from the existing
  `SSD/k8s_static_pv` policies.
- [ ] Do not manually create or modify children below CSI-owned parents.

### Service identity

- [ ] Create a dedicated `democratic-csi` TrueNAS account.
- [ ] Use a dedicated SSH key if SSH is required.
- [ ] Grant only the permissions supported by the chosen driver configuration.
- [ ] If passwordless sudo is required, document the commands the driver needs
  and verify the configuration survives TrueNAS updates.
- [x] Create a dedicated API key if the selected driver requires one. It is
  stored in 1Password as `truenas democratic csi api token`.
- [ ] Do not reuse the `truenas codex api key` discovery credential.
- [ ] Require HTTPS for API-key authentication.
- [ ] Replace the expired `truenas_default` certificate with a valid certificate
  trusted by CSI controller pods. Deferred by explicit operator decision for
  this homelab deployment on 2026-07-12.
- [x] Accept a TLS verification bypass for the TrueNAS management connection as
  a homelab-only exception. Scope it to `https://10.1.0.4:4443`; do not use the
  management address for NFS or iSCSI data traffic, and do not generalize the
  bypass to other integrations.
- [ ] Store credentials in the existing External Secrets/1Password workflow.
- [ ] Never commit API keys, passwords, or private SSH keys to Git.

### NFS

- [x] Confirm the TrueNAS NFS service is enabled and running.
- [ ] Use NFSv4.1 for the initial deployment.
- [ ] Restrict exports to the Kubernetes node networks.
- [ ] Ensure CSI-created exports advertise `10.254.0.4` and allow the actual
  source CIDRs observed from both clusters.
- [ ] Confirm UID/GID and root-squash behavior with a disposable workload.

### iSCSI

- [x] Enable and start the TrueNAS iSCSI service. Verified enabled at boot and
  `RUNNING` on 2026-07-12.
- [x] Create the first iSCSI portal listening only on `10.254.0.4:3260`.
  Portal database ID/tag: `1`.
- [x] Restrict initiator group `1` to the three verified Talos node IQNs:
  - `10.254.0.17`: `iqn.2017-11.dev.talos:4e3a52d4fb928f8a009a2f9c70fbeb94`
  - `10.254.0.18`: `iqn.2017-11.dev.talos:4714d27b48cc55b7982f5339c3ea3e5e`
  - `10.254.0.19`: `iqn.2017-11.dev.talos:3f79a44a7109c52fc7340c1c2c1fca4c`

  On TrueNAS 25.04, IP/CIDR authorization is a property of each target rather
  than the reusable initiator group. Democratic-csi `v1.9.5` does not send the
  target `auth_networks` property, so enforce IP-level restriction for TCP 3260
  at the network firewall in addition to the IQN allowlist.
- [ ] Decide whether to use CHAP and store its credentials externally.
- [ ] Choose a target/extent naming prefix unique to each cluster.
- [ ] Confirm every node in both target clusters can reach the portal before
  deploying the driver. Complete for all three nodes in the currently reachable
  cluster; the other cluster remains pending.
- [x] Record the numeric portal and initiator-group IDs required by the selected
  democratic-csi driver configuration: portal group `1`, initiator group `1`.

Do not enable multipath initially unless TrueNAS provides genuinely independent
paths through separate NICs and switching. Multiple portal addresses that share
the same physical failure domain do not provide meaningful redundancy.

## Phase 3: Talos preparation

### NFS

Test NFSv4.1 first without adding an extension. Avoid NFSv3 because its locking
services require additional node support.

### iSCSI

Every schedulable node in both clusters must include the official Talos
`iscsi-tools` system extension. Generate the installer from an Image Factory
schematic for Talos `v1.11.0`; do not use an extension image built for a
different Talos release. Add the extension to the schematic:

```yaml
customization:
  systemExtensions:
    officialExtensions:
      - siderolabs/iscsi-tools
```

- [ ] Inventory the current schematic/installer image for every node in both
  clusters. The three currently reachable `homelab` nodes are complete; the
  other cluster still needs verification.
- [x] Add `siderolabs/iscsi-tools` to the existing Talos `v1.11.0` schematic so
  all other extensions and customization remain unchanged for the currently
  reachable `homelab` cluster.
- [x] Submit the schematic to Image Factory and record its immutable schematic
  ID in the Talos configuration workflow for the currently reachable cluster:
  `c9078f9419961640c712a8bf2bb9174933dfcf1da383fd8ea2b7dc21493f8bac`.
- [x] Construct the installer reference as
  `factory.talos.dev/metal-installer/<schematic-id>:v1.11.0`, adjusted only if
  the nodes use a platform other than `metal`, for the currently reachable
  cluster.
- [ ] Confirm backups and cluster health before beginning the node rollout.
- [ ] Upgrade one drainable worker node to the new installer image.
- [x] Verify that the extension is active after reboot on `node07`, `node08`,
  and `node09`: all report `iscsi-tools v0.2.0`.
- [ ] Test iSCSI discovery and login through the CSI node integration.
- [ ] Roll the installer to the remaining workers one at a time using drain,
  upgrade/reboot, health verification, and uncordon between nodes.
- [ ] Roll control-plane nodes one at a time only after worker validation,
  preserving etcd quorum throughout.
- [ ] Verify every schedulable node reports the `iscsi-tools` extension before
  deploying the iSCSI StorageClass. Verified on all three nodes in the
  currently reachable cluster; the second target cluster is still pending.

Configure the democratic-csi iSCSI node pod for Talos:

```yaml
node:
  hostPID: true
  driver:
    extraEnv:
      - name: ISCSIADM_HOST_STRATEGY
        value: nsenter
      - name: ISCSIADM_HOST_PATH
        value: /usr/local/sbin/iscsiadm
    iscsiDirHostPath: /usr/local/etc/iscsi
    iscsiDirHostPathType: ""
```

The exact paths and chart keys must be checked against the pinned chart version
during implementation.

Installing the extension requires a Talos installer-image transition and node
reboot; applying a machine-config patch alone does not activate binaries that
are absent from the installed image. Keep the Talos base version at `v1.11.0`
during this change so the storage-enablement rollout is separate from a Talos
or Kubernetes upgrade.

## Phase 4: GitOps implementation

Implement the application in the repository's current `apps` and cluster
overlay structure rather than extending the legacy `cloud-underlay/rook`
layout. A proposed structure is:

```text
k8s/apps/democratic-csi/
├── base/
│   ├── namespace.yaml
│   ├── external-secret.yaml
│   └── kustomization.yaml
└── overlays/
    ├── control-plane/
    │   ├── kustomization.yaml
    │   └── values-nfs.yaml
    └── workload/
        ├── kustomization.yaml
        └── values-nfs.yaml
```

Implementation requirements:

- [x] Pin the Helm chart version: `0.15.1`.
- [x] Pin the democratic-csi image version: `v1.9.5` for controller and node.
- [x] Create the namespace explicitly.
- [x] Materialize driver credentials through an `ExternalSecret`.
- [x] Keep non-secret driver configuration in Git.
- [x] Use unique driver identities and parent datasets per cluster.
- [x] Create `truenas-nfs` without the default StorageClass annotation.
- [x] Set `reclaimPolicy: Retain` for the initial rollout.
- [x] Set NFS mount options explicitly, including NFSv4.1.
- [ ] Add a `VolumeSnapshotClass` only after confirming the snapshot controller
  is installed once in the cluster.
- [x] Render and validate both Kustomize/Helm overlays before Argo CD sync.
  Each renders 35 resources with no mutable `latest` driver tags, snapshot
  resources, or default StorageClass annotations. A server-side dry-run requires
  the target namespace to exist and is therefore deferred until sync/preflight.

TrueNAS 25.04 rejects the legacy REST `pool_dataset_update.dedup` field. Do not
set `zvolDedup` in the democratic-csi iSCSI configuration for this release;
allow zvols to inherit the pool's deduplication setting.

Do not change the existing `nfs-client` or `nfs-csi` default annotation during
this phase.

### Current Kubernetes storage inventory (2026-07-12)

Read-only inspection of the reachable `admin@homelab-1` cluster established:

- `node07`, `node08`, and `node09` are Ready, running Talos `v1.11.0` and
  Kubernetes `v1.32.0`.
- No `CSIDriver` objects are currently installed.
- `VolumeSnapshotClass`, `VolumeSnapshot`, and `VolumeSnapshotContent` CRDs are
  absent, so snapshot classes must remain disabled during the first rollout.
- Both `nfs-client` and `nfs-csi` are currently annotated as default
  StorageClasses. This pre-existing ambiguity is outside the initial CSI
  deployment and must not be changed as part of it.

## Phase 5: Acceptance testing

Use a dedicated namespace and disposable claims. Test NFS and iSCSI separately.

### Provisioning and data path

- [x] Dynamically create a PVC: `democratic-csi-test/iscsi-test`, 1 GiB RWO
  using `truenas-iscsi`.
- [x] Confirm the expected iSCSI PV was provisioned below the workload parent:
  `pvc-a5debbf9-1841-4d9e-9548-422e0f972b28`.
- [x] Mount the claim in a pod and write test data. Verified ext4 on `/dev/sda`.
- [x] Record checksums and verify them after pod recreation. Test payload SHA256:
  `5bdae9af624872bf9dd51ff0753a9f69c40305216f1d43f5a29e4b39bfbef5b1`.
- [x] Reschedule the pod to a different node and recheck the data. Initial mount
  succeeded on `node09`; detach and reattach succeeded on `node07`, and the
  checksum remained valid.
- [x] Confirm requested RWO access behavior. Kubernetes briefly reported the
  expected Multi-Attach protection while node09 detached, then attached the PV
  to node07 successfully.
- [ ] Expand the PVC and verify both Kubernetes and the filesystem size.

### Data management

- [ ] Create a CSI snapshot.
- [ ] Restore the snapshot to a new claim.
- [ ] Verify restored data by checksum.
- [ ] Test cloning if it will be used operationally.
- [ ] Delete a disposable claim and verify behavior under `Retain`.
- [ ] Manually exercise and document the retained-volume recovery procedure.

### Failure testing

- [ ] Reboot a Kubernetes node hosting the test workload.
- [ ] Drain and uncordon the node.
- [ ] Restart the TrueNAS storage service in a maintenance window.
- [ ] Reboot TrueNAS in a maintenance window.
- [ ] Confirm mounts recover and no stale iSCSI sessions remain.
- [ ] Review controller and node-plugin logs for repeated errors.

Do not use production data until all applicable tests pass.

## Phase 6: Workload migration

Migrate one low-risk workload first.

1. Back up the application and its existing volume.
2. Create a new PVC using `truenas-nfs` or `truenas-iscsi`.
3. Stop or quiesce the application.
4. Copy the data while preserving ownership, modes, timestamps, ACLs, and
   extended attributes where applicable.
5. Compare file counts, sizes, and checksums.
6. Point the workload at the new claim.
7. Observe it through at least one application restart and one node drain.
8. Keep the old volume unchanged for an agreed rollback period.

Select storage according to workload behavior:

- NFS: shared content, media, general application data, and workloads requiring
  `ReadWriteMany`.
- iSCSI: databases, VM disks, and filesystems expected to be mounted by one node
  at a time.

Do not attempt to change an existing PVC's `storageClassName` in place.

## Phase 7: Production adoption

- [ ] Migrate additional workloads in small batches.
- [ ] Document backup and restore procedures independently of CSI snapshots.
- [ ] Add monitoring for CSI controller/node availability and provisioning
  failures.
- [ ] Alert on TrueNAS pool health and capacity.
- [ ] Establish a minimum free-space threshold.
- [ ] Document credential rotation.
- [ ] Document TrueNAS and Talos upgrade compatibility checks.
- [ ] Decide whether `truenas-nfs` should become the default StorageClass.
- [ ] Remove the old default annotation before adding a new one; never leave two
  default StorageClasses intentionally.
- [ ] Retire the old NFS provisioner only after every old PV and PVC has been
  inventoried and assigned an owner or deletion plan.

CSI snapshots are not a substitute for backups. Retain an independent,
restore-tested backup or replication system for important data.

## Rollback strategy

During initial rollout, rollback consists of:

1. Stop new provisioning by removing or disabling the new StorageClass.
2. Leave the CSI controller and node plugin running while any CSI volumes remain
   mounted.
3. Move the pilot workload back to its preserved old volume.
4. Verify application data and operation.
5. Delete only disposable test claims and datasets.
6. Investigate before removing CSI resources or credentials.

Never uninstall the CSI node plugin while production volumes supplied by that
driver are mounted.

## Information required before implementation

- [x] Exact TrueNAS SCALE version: `25.04.2.6`
- [x] Exact Talos Linux version: `v1.11.0`
- [x] Exact Kubernetes version: `v1.32.0`
- [x] TrueNAS HTTPS connection: `https://10.1.0.4:4443` with TLS verification
  disabled by explicit operator acceptance for this homelab deployment.
- [ ] Replacement for the expired TrueNAS management certificate (deferred;
  not a deployment blocker by operator decision)
- [x] Single-disk `SSD` failure domain accepted for this homelab deployment.
- [x] CSI may use all available pool capacity without a dataset quota; preserve
  operational ZFS headroom through monitoring.
- [x] Target clusters: control plane and workload
- [x] Protocols: NFSv4.1 and iSCSI
- [x] Storage network: `10.254.0.0/24`; storage endpoint: `10.254.0.4`
- [ ] Node CIDRs and control-plane route/return-route details
- [ ] Desired ZFS snapshot and replication policy
- [x] TrueNAS API secret-store item name: `truenas democratic csi api token`;
  token property: `password`.
- [ ] Document ownership and rotation responsibility for the token.
- [ ] First pilot workload

## References

- [democratic-csi project documentation](https://github.com/democratic-csi/democratic-csi)
- [democratic-csi Helm charts](https://democratic-csi.github.io/charts/)
- [TrueNAS SCALE API documentation](https://www.truenas.com/docs/scale/api/)
- [TrueNAS SCALE 25.04 API documentation](https://www.truenas.com/docs/scale/25.04/api/)
- [TrueNAS SCALE 25.04 release notes](https://www.truenas.com/docs/scale/25.04/gettingstarted/scalereleasenotes/)
- [TrueNAS user and API-key management](https://www.truenas.com/docs/scale/credentials/users/manageusers/)
- [Talos Image Factory and system extensions](https://docs.siderolabs.com/talos/v1.12/platform-specific-installations/boot-assets)

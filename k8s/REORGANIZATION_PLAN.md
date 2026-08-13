# Kubernetes Repository Reorganization Plan

Status: **in progress**  
Prepared: **2026-08-07**  
Updated: **2026-08-13**
Scope: `k8s/` and the Cluster API experiments in `cluster-api/`

## Purpose

This plan controls the reorganization of the Kubernetes manifests. It protects the live management cluster and the unfinished tenant-cluster work.

The worktree contains many unrelated changes. Treat all unrelated changes as user work. Do not reset or remove them.

This document uses ASD-STE100 Simplified Technical English. Full compliance requires the official dictionary from <https://asd-ste100.org>.

## Required terminology

- The physical Kubernetes cluster is the **management cluster**.
- A Cluster API cluster on KubeVirt is a **tenant cluster**.
- `control plane` remains valid inside Cluster API and Kamaji resources.
- `management` identifies the role of the physical cluster.
- `tenant` identifies a cluster that the management cluster creates.
- `ephemeral` identifies a tenant lifecycle profile. It does not identify a second permanent cluster.

The repository has four responsibilities:

1. Bootstrap the management cluster.
2. Define Argo CD orchestration.
3. Store reusable platform and workload components.
4. Define tenant classes, profiles, and claims.

## Safety rules

CAUTION: Keep pruning disabled during each source-path change. Pruning can remove live resources before the new source owns them.

CAUTION: Do not change the management CNI during this reorganization. A CNI error can make the cluster unreachable.

CAUTION: Do not combine a component upgrade with a path change. This combination makes rollback and diagnosis difficult.

Use this sequence for each live component:

1. Copy the component to the new path.
2. Render the old path and the new path.
3. Make sure that both renders are equal.
4. Add an ApplicationSet exclusion for the old path.
5. Add an explicit ApplicationSet entry for the new path.
6. Make sure that the generated Application name does not change.
7. Publish the staging commit.
8. Save the live identities outside the repository.
9. Pause automated sync for the component.
10. Sync only the manual root with pruning disabled.
11. Make sure that the Application UID and owner do not change.
12. Make sure that the live source uses the new path.
13. Do a hard Argo refresh.
14. Review all drift before a component sync.
15. Sync the component with pruning disabled.
16. Make sure that the workload and storage identities do not change.
17. Restore automated sync for the component.
18. Remove the old path in a cleanup-only commit.
19. Publish the cleanup commit.
20. Sync only the root with pruning disabled.

If Argo shows an unexpected prune, replacement, or shared-resource warning, stop the migration.

## Current live state

The state in this section was current after the ExternalDNS, Home Assistant, Loki, and Unpoller migrations on 2026-08-13.

- The manual root Application is `argocd`.
- The root owns only `apps-control-plane`.
- The root has no automated sync policy.
- `apps-control-plane` uses `applicationsSync: create-update`.
- `apps-control-plane` uses `preserveResourcesOnDeletion: true`.
- `apps-control-plane` has `resources-finalizer.argocd.argoproj.io`.
- The inventory contains 27 Applications.
- The ApplicationSet generates 25 Applications.
- Argo reports zero shared-resource warnings.
- Cilium and Argo self-management remain deferred.
- Tinkerbell remains paused and has no workload resources.
- The management cluster has no CAPI Clusters or Machines.
- The management cluster has no Kamaji `TenantControlPlane` objects.
- The management cluster has no KubeVirt VMs or VMIs.

The initial live export is in `/tmp/k8s-homelab-reorganization-2026-08-11.4GZ5jo/`.

## Initial repository findings

The repository was already in a partial migration on 2026-08-07. Several old and new GitOps roots had overlapping ownership.

The overlapping paths included:

- `k8s/0-cluster-applicationSets/`
- `k8s/applicationSets/`
- `k8s/clusters/`
- `k8s/cloud-underlay/`
- `k8s/secret-management/`
- `k8s/1-control-plane/`
- `k8s/1-workload-cluster/`
- standalone `Application` files in `k8s/apps/*.yaml`
- root application directories such as `k8s/multus/` and `k8s/velero/`

These initial composition commands failed:

```sh
kustomize build k8s/clusters/control-plane
# Fails because nested Kustomizations reference files outside their load root.

kustomize build k8s/clusters/workload
# Fails because apps/teams/demo/overlays/workload does not exist.
```

The individual Cluster API, Kamaji, and KubeVirt overlays rendered at that time:

```sh
kustomize build k8s/apps/cluster-api/overlays/control-plane
kustomize build --enable-helm k8s/apps/kamaji/overlays/control-plane
kustomize build k8s/apps/kubevirt/overlays/control-plane
```

The initial structure had these defects:

- `k8s/apps/kubevirt.yaml` used a path without a root `kustomization.yaml`.
- The Cluster API base mixed provider installation and a KRO `ResourceGraphDefinition`.
- The repository contained an RGD but did not install KRO.
- Cilium and Kube-OVN selected the same tenant clusters.
- Argo wrappers and deployed resources shared the `k8s/apps/` tree.
- Component directories used both `base/` and `bases/`.
- The repository contained obsolete Kamaji and KubeVirt proof-of-concept files.

## Credential controls

Phase 0 removed generated kubeconfigs, age private keys, and plaintext repository credentials from the worktree.

Phase 0 also added ignore rules and scanned the worktree and Git history. The obsolete tenant kubeconfig was not retained.

The remaining Talos secrets file moved to this external path:

`/tmp/k8s-homelab-reorganization-2026-08-07/credentials/cluster-api-minimal-talos-secrets.yaml`

Use these rules:

- Store generated kubeconfigs outside Git.
- Store private age keys outside Git.
- Store only secret references, encrypted data, or public recipients in Git.
- If another system used or copied a credential, rotate it.
- Search Git history before you classify a credential as uncommitted.
- Never write secret contents in this plan or a progress record.

## Target structure

```text
k8s/
├── REORGANIZATION_PLAN.md
├── bootstrap/
│   └── argocd/
│       ├── README.md
│       └── root-application.yaml
├── argocd/
│   ├── projects/
│   ├── applications/
│   │   └── management/
│   └── applicationsets/
│       ├── management/
│       ├── tenant-addons/
│       └── tenant-workloads/
├── apps/
│   ├── platform/
│   │   └── <component>/
│   └── workloads/
│       └── <component>/
└── fleet/
    ├── classes/
    ├── profiles/
    ├── claims/
    │   └── persistent/
    └── examples/
```

Use this component structure:

```text
<component>/
├── README.md
├── base/
│   └── kustomization.yaml
└── overlays/
    ├── management/
    │   └── kustomization.yaml
    └── tenant/
        └── kustomization.yaml
```

## Directory ownership

### `bootstrap/`

This directory contains only manual resources that establish GitOps. It points to Argo CD and the single root Application.

Do not store normal application manifests in this directory.

### `argocd/`

This directory contains `Application`, `ApplicationSet`, and `AppProject` resources. Management Applications use `https://kubernetes.default.svc`.

Tenant ApplicationSets select registered tenant clusters by label. They must not select the management cluster.

### `apps/`

This directory contains deployable Kubernetes components. It does not contain the central Argo orchestration root.

Use `apps/platform/<name>` for cluster capabilities and shared controllers. Use `apps/workloads/<name>` for user services.

Use `base/` for shared resources. Use `overlays/management/` and `overlays/tenant/` for role-specific resources.

### `fleet/`

This directory contains the API and policy for CAPI-managed clusters. `classes/` contains KRO RGDs or future CAPI ClusterClasses.

`profiles/` contains tenant capabilities and bootstrap add-ons. `claims/persistent/` contains long-lived Git-managed clusters.

`examples/` contains non-reconciled examples. Ephemeral claims normally come from a controlled pipeline or API.

## Tenant lifecycle

```text
Ephemeral cluster request
    -> KRO claim or CAPI resources
    -> Kamaji hosted control plane
    -> CAPK KubeVirt worker VMs
    -> bootstrap CNI and required add-ons
    -> Argo CD cluster registration with fleet labels
    -> tenant ApplicationSets
    -> expiry or explicit removal
    -> Argo deregistration and CAPI or VM cleanup
```

Each ephemeral request must contain:

- owner
- purpose
- creation time
- expiry time or maximum lifetime
- tenant profile
- Kubernetes version
- resource size
- pod CIDR
- service CIDR

Use these Argo cluster-secret labels:

```yaml
fleet.fondevilla.io/role: tenant
fleet.fondevilla.io/profile: ephemeral
fleet.fondevilla.io/cni: cilium
fleet.fondevilla.io/owner: victor
```

Do not install tenant workloads before the tenant API and Cilium are healthy.

## Network decision

Cilium is the primary CNI for management and tenant clusters. This decision is final for the first platform version.

- Do not deploy Kube-OVN as a second primary CNI.
- Do not deploy Multus as a second primary CNI.
- Use Kube-OVN or Multus only in an explicit Cilium chain.
- Install a chained CNI only after Cilium is healthy.
- Do not use a generic `type=workload` selector for chained CNIs.
- Document interface, IPAM, route, and cleanup ownership for each chained CNI.

Use explicit profile names such as `cilium-multus` or `cilium-kube-ovn`.

## Management dependency order

| Tier | Components | Requirement |
| --- | --- | --- |
| Bootstrap | Argo CD root | Manual installation, then self-management |
| Foundation | cert-manager, secrets, NFD | Ready before later webhooks and operators |
| Virtualization | KubeVirt, CDI | Ready before CAPK creates VMs |
| CAPI core | CAPI core, bootstrap, control plane, CAPK | Provider installation only |
| Hosted control plane | Kamaji runtime and datastore | CRDs and datastore Ready |
| Kamaji provider | CAPI provider for Kamaji | Install after CAPI and Kamaji |
| Abstraction | KRO | Install before the RGD |
| Fleet class | `KamajiKubevirtCluster` RGD | Keep outside the CAPI provider base |
| Instances | Persistent and ephemeral claims | Last tier because removal is destructive |

## Phase 0: Protect credentials and record state

Status: **complete**

- [x] Move generated kubeconfigs outside the repository.
- [x] Move private age keys outside the repository.
- [x] Remove the obsolete tenant kubeconfig.
- [x] Add explicit ignore rules.
- [x] Scan the worktree and Git history for secrets.
- [x] Save the worktree state in local notes.
- [x] Export Argo, CAPI, Kamaji, VM, and VMI state.
- [x] Record Application names, paths, policies, and health.

Read-only commands:

```sh
git status --short
git ls-files | rg '(kubeconfig|credentials|age-key|secret)'
kubectl -n argocd get applications,applicationsets -o wide
kubectl get clusters,machinedeployments,machinesets,machines -A
kubectl get kamajicontrolplanes,tenantcontrolplanes -A
kubectl get vm,vmi -A
```

Phase gate:

- [x] No plaintext private credential remains in a commit candidate.
- [x] Local notes contain a recoverable pre-migration state.

## Phase 1: Define the architecture

Status: **complete**

- [x] Use the terms management, tenant, and ephemeral.
- [x] Create the target top-level directories.
- [x] Document each directory owner.
- [x] Keep Argo away from new paths during scaffolding.
- [x] Classify `cloud-underlay` as a temporary management bootstrap surface.
- [x] Move platform capabilities out of `cloud-underlay` one component at a time.
- [x] Plan LibreNMS and Zot as workloads.

## Phase 2: Establish one Argo root

Status: **complete for root activation**

- [x] Create the normalized Argo directories.
- [x] Copy the live `apps-control-plane` ApplicationSet.
- [x] Preserve live Application names, destinations, paths, and policies.
- [x] Add ApplicationSet deletion controls.
- [x] Enable per-ApplicationSet policy overrides.
- [x] Remove five duplicate `platform-*` Applications without pruning.
- [x] Transfer 110 tracking annotations to the retained Applications.
- [x] Correct the Tinkerbell chart comparison error.
- [x] Create the manual root Application.
- [x] Sync the root with pruning disabled.
- [ ] Restore automated sync only after each component migration.

The parity root uses commit `1bb3012`. It owns one protected ApplicationSet and does not use automated sync.

Tinkerbell uses the corrected chart data from `7677d12`. It remains paused and has no workloads.

The duplicate-ownership rollback data is in `/tmp/k8s-homelab-argo-handoff-2026-08-11.PmrVpI/`.

## Phase 3: Normalize components

Status: **in progress**

General tasks:

- [ ] Classify each component as `platform` or `workloads`.
- [ ] Move one component at a time.
- [ ] Replace `bases/` with `base/` during each component move.
- [ ] Replace `overlays/control-plane/` with `overlays/management/` for management resources.
- [ ] Replace `overlays/workload/` with `overlays/tenant/` only for reusable tenant resources.
- [ ] Change each Argo source path with the safe sequence.
- [ ] Render both paths before you remove the old path.
- [x] Correct the KubeVirt Application source.

Classification:

| Components | Class |
| --- | --- |
| Argo CD, cert-manager, Cilium, ESO, 1Password Connect | Platform foundation |
| NFD, KubeVirt, CDI | Platform virtualization |
| Cluster API, CAPK, Kamaji, KRO | Platform cluster lifecycle |
| Rook, democratic-csi, storage classes | Platform storage |
| Tinkerbell | Platform provisioning |
| Prometheus, Loki, Alloy | Platform observability |
| Actual Budget, Home Assistant, Mosquitto, Zigbee2MQTT | Workloads |

Component gate:

1. Render the new path.
2. Make sure that the old and new renders are equal.
3. Make sure that Argo shows no unexpected replacement or prune.
4. Make sure that the Application is Healthy and Synced from the new path.
5. Remove the old path only after all prior steps pass.

### Completed Phase 3 migrations

| Component | Staging commits | Cleanup commit | Result |
| --- | --- | --- | --- |
| 1Password Connect | `aa7c279` | `12fe5d2` | Four resources synced. Application and pod UIDs stayed equal. |
| External Secrets Operator | `30ab11a` | `80cf100` | 49 resources synced. Three pod UIDs stayed equal. |
| cert-manager | `937beaf`, `e54e3d1` | `8b8d283` | 52 resources synced. Three pod UIDs stayed equal. |
| Node Feature Discovery | `2397e9f` | `19f4be7` | 18 resources synced. Four pod UIDs stayed equal. |
| KubeVirt and CDI | `b6ca658`, `e01941f` | `92ee432` | 20 resources synced. Twelve pod UIDs stayed equal. |
| Local Path Provisioner | `801845b` | `99dfbf5` | Nine resources synced. Deployment and pod UIDs stayed equal. |
| Prometheus CRDs | `b7bd2b4` | `4df1157` | Outer Application synced. Child and ten CRD UIDs stayed equal. |
| Actual Budget | `3429a44` | `18ec096` | Seven resources synced. Workload and storage UIDs stayed equal. |
| Alloy | `0de110c` | `6b576f2` | Seven resources synced. The Application, DaemonSet, and pod UIDs stayed equal. |
| HWPO Flex | `0de110c` | `6b576f2` | Six resources synced. Workload and storage UIDs stayed equal. |
| ExternalDNS | `c158114` | `9db7ba4` | 15 resources synced. The Application, Deployment, pod, and ExternalSecret UIDs stayed equal. |
| Home Assistant | `c158114` | `9db7ba4` | Nine resources synced. Workload, ExternalSecret, and storage UIDs stayed equal. |
| Loki | `c158114` | `9db7ba4` | 11 resources synced. Workload, ExternalSecret, and storage UIDs stayed equal. |
| Unpoller | `c158114` | `9db7ba4` | Five resources synced. The Application, Deployment, pod, and ExternalSecret UIDs stayed equal. |

All completed migrations preserved these live values:

- 27 Applications
- 25 generated Applications
- zero shared-resource warnings
- original Application UIDs and owners

### Important Phase 3 findings

The API-aware ESO render contains 49 objects. A plain local render contains only 44 objects.

cert-manager had 27 incorrect tracking annotations on cluster-scoped objects. The migration corrected only those annotations.

CDI 1.63.1 owns `.spec.versions` on `cdis.cdi.kubevirt.io`. Commit `e01941f` removes obsolete `v1alpha1` from the normalized render.

Prometheus CRDs use a nested Application. The outer sync did not operate the child Application or replace its CRDs.

NFS migration requires extra storage checks. Five Bound volumes use its StorageClass.

Prometheus migration remains deferred because the live Application is Progressing and OutOfSync.

Cilium and Argo self-management remain deferred by policy.

### Completed Phase 3 batch: Alloy and HWPO Flex

Staging commit `0de110c` adds these normalized paths:

- `k8s/apps/platform/alloy/overlays/management`
- `k8s/apps/workloads/hwpo-flex/overlays/management`

The Alloy old and new renders are byte-identical. Both renders contain seven resources.

The HWPO Flex old and new renders are byte-identical. Both renders contain six resources.

The live migration kept these identities:

- Both Application UIDs
- The Alloy DaemonSet UID
- Both Alloy pod UIDs
- The HWPO Flex Deployment UID
- The HWPO Flex pod UID
- The HWPO Flex PV and PVC UIDs

The HWPO Flex PV and PVC remained Bound. The PV reclaim policy remained `Retain`.

Both Applications remained Healthy and Synced through two hard-refresh cycles.

The explicit sync requests used `prune: false`. Argo status retained stale `prune: true` data from the prior operations.

The sync results contained only the expected resources. No resource was removed or replaced.

Automated prune and self-heal are active again for both Applications.

Cleanup commit `6b576f2` removes both old management paths and their ApplicationSet exclusions.

Commit `6328c75` records the result. The root and both Applications are Healthy and Synced at this revision.

The final inventory contains 27 Applications. The ApplicationSet generates 25 Applications. Argo reports zero shared-resource warnings.

### Previous Phase 3 batch: ExternalDNS, Home Assistant, Loki, and Unpoller

Staging commit `c158114` adds the normalized paths and explicit ExternalSecret defaults.

This batch uses these normalized paths:

- `k8s/apps/platform/external-dns/overlays/management`
- `k8s/apps/workloads/home-assistant/overlays/management`
- `k8s/apps/platform/loki/overlays/management`
- `k8s/apps/platform/unpoller/overlays/management`

Before the migration, all four Applications were Healthy. Each Application reported only its ExternalSecret as OutOfSync.

Kubernetes adds default fields to each ExternalSecret. The normalized source includes these explicit values.

The old and new renders are byte-identical after this correction:

| Component | Resources | Render SHA-256 |
| --- | ---: | --- |
| ExternalDNS | 15 | `d985c213f3eea163a056f516bf09c074b7c1568d71bb36faf20afcad8d3d19bf` |
| Home Assistant | 9 | `f590cc4afefdc58265ddf953630155025edd3e7dd4ca8b0fcef1d69e8a5e04f2` |
| Loki | 11 | `d0c32e1a772aaa2ee7cbe4f59b7da65ee734957e9124933379e5db7f674c0bbd` |
| Unpoller | 5 | `83b3785a0ae377cf9e184ba702b2acdd2ca234f36acf2cdf6bd04e01d8e23712` |

The server-side diff is empty for all four renders. Home Assistant and Loki produce existing Pod Security warnings only.

The saved state is in `/tmp/k8s-homelab-externaldns-ha-loki-unpoller-path-switch-2026-08-12.T3r4kL`.

The live switch kept these resources:

- All four Application UIDs
- The ExternalDNS Deployment, pod, and ExternalSecret UIDs
- The Home Assistant Deployment, pod, ExternalSecret, PV, and PVC UIDs
- The Loki StatefulSet, pod, ExternalSecret, PV, and PVC UIDs
- The Unpoller Deployment, pod, and ExternalSecret UIDs

All four explicit sync operations used `prune: false`. The sync results contained 15, 9, 11, and 5 resources.

All four Applications remained Healthy and Synced through two hard-refresh cycles.

Automated prune and self-heal are active again for all four Applications.

The Home Assistant and Loki PVs and PVCs remained Bound. Both PV reclaim policies remained `Retain`.

Cleanup commit `9db7ba4` removes all four old paths and their ApplicationSet exclusions.

The inventory contains 27 Applications. The ApplicationSet generates 25 Applications. Argo reports zero shared-resource warnings.

Next procedure:

1. Publish `9db7ba4` and the plan update.
2. Make sure that all four old paths are absent from `main`.
3. Do a hard refresh of all four Applications.
4. Make sure that all four Applications remain Healthy and Synced.
5. Sync only `argocd` with pruning disabled.
6. Make sure that all four obsolete live exclusions are absent.
7. Make sure that all saved UIDs remain equal.

### Current Phase 3 staging batch: MeshCentral, Mosquitto, NFS Subdirectory Provisioner, and Zigbee2MQTT

This batch uses these normalized paths:

- `k8s/apps/workloads/meshcentral/overlays/management`
- `k8s/apps/workloads/mosquitto/overlays/management`
- `k8s/apps/platform/nfs-subdir/overlays/management`
- `k8s/apps/workloads/zigbee2mqtt/overlays/management`

The old MeshCentral and Mosquitto sources omitted the names of their bound volumes.

Argo could not change the immutable `volumeName` field on three PVCs. The corrected sources specify the existing volume names.

All old and new renders are byte-identical after this correction:

| Component | Resources | Render SHA-256 |
| --- | ---: | --- |
| MeshCentral | 7 | `8a23ddf2907abd7c0565e1d04663b0cea9ff1704b0cfce96777531752e1ec02a` |
| Mosquitto | 7 | `a0062cc55448b94cc0994b975d0965697ca3584209eea664d69d823128847c78` |
| NFS Subdirectory Provisioner | 8 | `cbe5181863f2d03b83d18a9aca9014f936df7217491be10204d0eb4aed54f031` |
| Zigbee2MQTT | 5 | `3827911a6ab3f4d7312e00adb3eed46f873cbdd9ce8b8ba155017a3c305d773c` |

The NFS and Zigbee2MQTT server-side diffs are empty. They produce existing Pod Security warnings only.

The MeshCentral and Mosquitto diffs contain only the Argo tracking annotations on the corrected PVCs.

The pre-switch Application UIDs are:

- MeshCentral: `e252c7ba-60ea-48f2-953c-9e3a4f922f10`
- Mosquitto: `85cee037-d712-4096-bb7e-25eed4cdcf95`
- NFS Subdirectory Provisioner: `8ba5aeca-5ac1-4c00-952a-0d78a0a2c023`
- Zigbee2MQTT: `a73698bf-0e1c-4098-9697-70c49f0302ab`

The NFS provisioner has five Bound volumes. They contain three Kamaji etcd volumes, one Loki volume, and one Zot volume.

The `nfs-client` StorageClass UID is `9abd5a22-a683-4bad-8d74-b0f6e7db7f5d`.

Next procedure:

1. Publish the staging commit.
2. Pause automated sync for all four Applications.
3. Sync only `argocd` with pruning disabled.
4. Make sure that all four Application UIDs and owners stay equal.
5. Do a hard refresh for all four Applications.
6. Review all planned operations.
7. Sync each component with pruning disabled.
8. Make sure that all workload and storage UIDs stay equal.
9. Restore automated sync for all four Applications.
10. Remove only the old management paths in a cleanup commit.

CAUTION: The old NFS tenant overlay still uses the old shared base. Keep that base until the tenant overlay moves.

### Previous Phase 3 migration: Actual Budget

Staging commit `3429a44` adds this normalized path:

`k8s/apps/workloads/actualbudget/overlays/management`

The commit also extends the ApplicationSet name template. Both `platform/` and `workloads/` paths now preserve existing component names.

The old and new renders are byte-identical. Both renders contain seven resources.

The live state before migration was:

- Application: `in-cluster-actualbudget`
- Application UID: `c226065d-f103-4910-88e1-15a71d39ecb7`
- StatefulSet UID: `4155fb22-ae2e-4379-8076-c31084ed25c5`
- Pod UID: `7c10ffa3-9e8c-48d6-a847-b960d02db4f9`
- PVC UID: `9dc81c23-07f1-4045-9e8f-69d43681a8ed`
- PV UID: `505ae57b-5f80-4481-8c3e-8f9b214bc61f`
- PV reclaim policy: `Retain`
- Application state: Healthy and Synced
- Workload state: Ready
- Storage state: Bound

The migration kept all listed UIDs. The PV and PVC remained Bound. The StatefulSet and pod remained Ready.

The seven-resource sync succeeded with pruning disabled. Automated prune and self-heal are active again.

Cleanup commit `18ec096` removes the old path and the obsolete ApplicationSet exclusion.

## Phase 4: Separate the cluster lifecycle

Status: **partly complete**

- [x] Keep CAPI and CAPK installation in the CAPI platform component.
- [x] Split the Kamaji CAPI provider from the CAPI base.
- [x] Keep the Kamaji runtime in a separate component.
- [x] Add a KRO platform component.
- [x] Move the RGD to `k8s/fleet/classes/kamaji-kubevirt/`.
- [x] Remove the obsolete Kamaji and KubeVirt proof of concept.
- [ ] Move useful experiments to `fleet/examples/`.
- [ ] Keep all examples outside Argo discovery patterns.
- [ ] Make sure that the explicit Kamaji provider arguments remain.
- [ ] Make sure that Argo does not render the Kamaji teardown hook as a normal Job.
- [ ] Make sure that a clean installation creates `DataStore/default` in the correct order.
- [ ] Replace the manual Flannel step with automated Cilium bootstrap.

Keep KRO as the first request facade. Evaluate a native CAPI ClusterClass after Kamaji and CAPK template validation.

## Phase 5: Implement one tenant profile

Status: **partly complete**

Decisions:

- [x] Use Cilium as the primary tenant CNI.
- [x] Use CAPI `ClusterResourceSet` for the minimal bootstrap bundle.
- [x] Enable `ClusterResourceSet=true` in the staged CAPI controller.
- [ ] Select all mandatory add-ons before Argo registration.

Tasks:

- [x] Add profile labels to the CAPI and KRO claim schema.
- [ ] Install Cilium automatically.
- [ ] Wait until tenant nodes and Cilium are Ready.
- [ ] Register the CAPI kubeconfig in Argo without a Git copy.
- [ ] Add the fleet labels to the registration.
- [ ] Make sure that tenant ApplicationSets exclude the management cluster.
- [x] Disable the generic Kube-OVN ApplicationSet.
- [x] Make Multus an explicit Cilium-chain option.
- [ ] When CAPI removes the Cluster, remove the Argo registration.

The current Cilium tenant overlay cannot serve dynamic Kamaji tenants. It contains these fixed values:

- `cluster.name=workload-cluster`
- `k8sServiceHost=localhost`

Define a per-tenant API endpoint method before you build the shared `ClusterResourceSet` payload.

## Phase 6: Add ephemeral controls

Status: **not started**

- [ ] Define a request contract with owner, purpose, expiry, size, version, CIDRs, and profile.
- [ ] Select CI, an API, or short-lived reviewed pull requests as the request source.
- [ ] Implement expiry control. CAPI does not infer a TTL from `ephemeral`.
- [ ] If ownership or expiry data is absent, block removal.
- [ ] Add quotas for VM CPU, memory, storage, tenant count, and LoadBalancer IPs.
- [ ] Add a removal test for CAPI, VMs, Secrets, Argo registration, and tenant namespaces.

Keep reusable classes and profiles in Git. Create ephemeral claims through a controlled pipeline or API.

## Phase 7: Remove legacy roots

Status: **in progress**

Removal candidates:

- [x] `k8s/0-cluster-applicationSets/`
- [x] `k8s/applicationSets/`
- `k8s/1-control-plane/`
- `k8s/1-workload-cluster/`
- [x] `k8s/clusters/workload/`
- [x] the old `k8s/clusters/control-plane/`
- duplicate root application directories
- obsolete Cluster API experiments

Use this procedure for each candidate:

1. Make sure that no live Application uses the path.
2. Use `rg` to find all Kustomize and Argo references.
3. Make sure that the new path contains equal resources.
4. Observe two clean Argo sync cycles.
5. Remove the old path in a dedicated commit.

## Repository validation

### Static validation

- [ ] Render every Kustomize overlay.
- [ ] Render each Helm overlay with `--enable-helm`.
- [ ] Validate the rendered resources against the selected schemas.
- [ ] Make sure that every Argo source is a supported manifest source.
- [ ] Make sure that no Kustomization requires disabled load restrictions.
- [ ] Make sure that Git tracks no generated credential.
- [ ] Make sure that ignore rules cover all generated credentials.

Suggested commands:

```sh
kustomize build <overlay>
kustomize build --enable-helm <helm-overlay>
kubeconform -strict -summary <rendered-manifests>
```

### GitOps validation

- [ ] Render the Argo root.
- [ ] Compare desired and live Application names.
- [ ] Compare destinations and source paths.
- [ ] Review each prune before a sync.
- [ ] Keep automated pruning disabled during each path change.
- [ ] Make sure that tenant selectors exclude the management cluster.

### Tenant validation

1. Create one disposable claim.
2. Make sure that the Kamaji control plane is Ready.
3. Make sure that the CAPK VM and VMI are Ready.
4. Make sure that the worker node is Ready.
5. Make sure that Cilium is healthy.
6. Make sure that Argo registration and labels are correct.
7. Make sure that tenant add-ons become Healthy.
8. Operate DNS, Service, storage, and outbound-network tests.
9. Remove or expire the claim.
10. Make sure that Argo removes the cluster registration.
11. Make sure that CAPI removes all tenant VMs and resources.
12. Make sure that the management cluster remains Healthy.

## Safe commit sequence

1. Add documentation and credential ignore rules.
2. Add empty target directories and README files.
3. Add the protected Argo root without activation.
4. Activate the root and preserve Application names.
5. Move foundation components one at a time.
6. Move virtualization components one at a time.
7. Split and move the cluster-lifecycle stack.
8. Add the tenant bootstrap and profile flow.
9. Add ephemeral controls.
10. Remove legacy paths in cleanup-only commits.

Do not use one large rename commit. A large commit makes Argo review and rollback difficult.

## Decisions

| Decision | Result | Status |
| --- | --- | --- |
| Cluster terms | Management and tenant. Ephemeral is a profile. | Proposed |
| Primary tenant CNI | Cilium. Kube-OVN and Multus are chain options only. | Decided |
| Request abstraction | Keep KRO for the first version. | Proposed |
| Native ClusterClass | Evaluate after repository cleanup. | Deferred |
| Bootstrap add-ons | Use a minimal Cilium `ClusterResourceSet`. Use Argo for higher layers. | Decided |
| Ephemeral request storage | Use a pipeline or API. | Proposed |
| `cloud-underlay` | Keep it only as a temporary bootstrap surface. | Decided |
| Application size | Use one Application for each independent component. | Proposed |

## Rollback locations

| Change | Local rollback path |
| --- | --- |
| Initial live export | `/tmp/k8s-homelab-reorganization-2026-08-11.4GZ5jo/` |
| Ownership handoff | `/tmp/k8s-homelab-argo-handoff-2026-08-11.PmrVpI/` |
| Root activation | `/tmp/k8s-homelab-root-bootstrap-2026-08-12.VjoTg4` |
| 1Password Connect | `/tmp/k8s-homelab-1password-path-switch-2026-08-12.sMEEZ3` |
| External Secrets Operator | `/tmp/k8s-homelab-eso-path-switch-2026-08-12.Ee0w75` |
| cert-manager | `/tmp/k8s-homelab-cert-manager-path-switch-2026-08-12.v5qIPL` |
| Node Feature Discovery | `/tmp/k8s-homelab-nfd-path-switch-2026-08-12.Nbv3SP` |
| KubeVirt and CDI | `/tmp/k8s-homelab-kubevirt-path-switch-2026-08-12.4yZc7r` |
| Local Path Provisioner | `/tmp/k8s-homelab-local-provisioner-path-switch-2026-08-12.Bv5o1H` |
| Prometheus CRDs | `/tmp/k8s-homelab-prometheus-crds-path-switch-2026-08-12.joQUfv` |
| Actual Budget | `/tmp/k8s-homelab-actualbudget-path-switch-2026-08-12.v4VZCi` |
| Alloy and HWPO Flex | `/tmp/k8s-homelab-alloy-hwpo-path-switch-2026-08-12.J2IJ3R` |
| ExternalDNS, Home Assistant, Loki, and Unpoller | `/tmp/k8s-homelab-externaldns-ha-loki-unpoller-path-switch-2026-08-12.T3r4kL` |

These paths are local and temporary. Do not depend on them as permanent backup storage.

## Resume procedure

1. Read this plan.
2. Operate `git status --short`.
3. Treat unrelated worktree changes as user work.
4. Make sure that credential-risk files remain absent or ignored.
5. Read the live Argo state before any sync or removal.
6. Start with the current Phase 3 candidate.
7. Update this plan after each material change.
8. If Argo shows an unexpected prune or replacement, stop.

## References

- Cluster API `ClusterResourceSet`: <https://main.cluster-api.sigs.k8s.io/tasks/cluster-resource-set>
- Cluster API ClusterClass: <https://cluster-api.sigs.k8s.io/tasks/experimental-features/cluster-class/>
- Argo CD cluster generator: <https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Cluster/>
- Argo CD matrix generator: <https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Matrix/>
- Argo CD deletion controls: <https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Controlling-Resource-Modification/>

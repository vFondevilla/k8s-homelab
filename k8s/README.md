# Kubernetes Directory Standard

This directory contains the Kubernetes state for the homelab.

This document defines the required repository structure. It also explains where each type of resource belongs.

The repository is in a controlled migration. Some legacy paths remain because live Argo CD Applications still use them.

Read [REORGANIZATION_PLAN.md](REORGANIZATION_PLAN.md) before you move a live component. The plan records migration state, safety gates, and rollback data.

## Terminology

Use these terms in all new files and documentation:

- **Management cluster**: The physical Kubernetes cluster that operates Argo CD, Cluster API, Kamaji, KubeVirt, and shared services.
- **Tenant cluster**: A Kubernetes cluster that Cluster API creates on the management cluster.
- **Control plane**: The Kubernetes API and controller role inside Cluster API or Kamaji resources.
- **Ephemeral**: A tenant lifecycle profile with an expiry rule.
- **Platform component**: A controller or capability that supports a cluster.
- **Workload component**: A service that users consume.

Do not use `control-plane` as a name for the management-cluster role in new directory paths.

Use `management` and `tenant` for new overlay names.

## Core rules

The `k8s/` directory has four responsibilities:

1. Bootstrap GitOps on the management cluster.
2. Define Argo CD orchestration.
3. Store reusable platform and workload components.
4. Define tenant classes, profiles, claims, and examples.

Each responsibility has one owner directory:

| Responsibility | Owner directory |
| --- | --- |
| Manual GitOps bootstrap | `bootstrap/` |
| Argo CD orchestration | `argocd/` |
| Deployable Kubernetes resources | `apps/` |
| Tenant lifecycle API | `fleet/` |

Do not create a second owner for the same resource.

Do not put Argo CD wrapper resources beside their deployed resources.

Do not put normal application resources in the bootstrap directory.

Do not put generated credentials or kubeconfigs in this repository.

## Required target structure

New work must use this structure:

```text
k8s/
├── README.md
├── REORGANIZATION_PLAN.md
├── bootstrap/
│   └── argocd/
│       ├── README.md
│       └── root-application.yaml
├── argocd/
│   ├── kustomization.yaml
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

The following sections define each part of this structure.

## `bootstrap/`: manual GitOps entry point

The `bootstrap/` directory contains the minimum resources that establish GitOps.

The current entry point is `bootstrap/argocd/root-application.yaml`. An operator applies this resource manually.

The root Application has these responsibilities:

- It uses the `argocd` namespace.
- It points to `k8s/argocd` on the `main` branch.
- It targets `https://kubernetes.default.svc`.
- It does not enable automated synchronization.

Only bootstrap resources belong in this directory.

Do not add component Deployments, Services, operators, workloads, or tenant claims here.

### Bootstrap procedure

1. Render the Argo root before you apply the bootstrap resource.
2. Compare the render with the live Argo inventory.
3. Apply the root Application without pruning.
4. Review each generated Argo resource.
5. Enable more root resources only after that review.

Use this command to render the active Argo root:

```sh
kustomize build --enable-helm k8s/argocd
```

Use this command to apply the manual bootstrap resource:

```sh
kubectl apply -f k8s/bootstrap/argocd/root-application.yaml
```

CAUTION: Do not enable automated pruning on the root during a source-path migration. An incorrect path can remove live resources.

## `argocd/`: orchestration

The `argocd/` directory contains only these Argo CD resource types:

- `Application`
- `ApplicationSet`
- `AppProject`

This directory defines where resources deploy. The `apps/` and `fleet/` directories define what Argo CD deploys.

The root `argocd/kustomization.yaml` controls which orchestration resources are active.

A file elsewhere in `argocd/` is not active only because the file exists. A Kustomization must include the file.

### Current root activation

The active root currently includes only `argocd/applicationsets/management/`.

Management Applications and tenant ApplicationSets remain staged outside the root during the migration.

Add a staged directory to the root only after a live inventory review.

### `argocd/projects/`

This directory contains `AppProject` resources.

Use an `AppProject` to restrict source repositories, destinations, and permitted resource types.

Do not put Applications or component resources in this directory.

### `argocd/applications/management/`

This directory contains explicit Applications for the management cluster.

If a component needs special source behavior or dependency control, use an explicit Application.

Examples include these cases:

- A component uses multiple sources.
- A component installs a fleet class.
- A component needs a special synchronization policy.
- A component cannot use a directory generator safely.

Management Applications use `https://kubernetes.default.svc` as their destination server.

Preserve the Application name during a source-path migration. A name change creates a different Argo CD object.

### `argocd/applicationsets/management/`

This directory contains ApplicationSets for management-cluster components.

The current `apps-control-plane` ApplicationSet selects the cluster with the legacy `type=control-plane` label.

The ApplicationSet discovers both legacy overlays and normalized overlays during the migration.

Normalized management sources use these patterns:

```text
k8s/apps/platform/*/overlays/management
k8s/apps/workloads/*/overlays/management
```

The generated Application name must remain `<cluster-name>-<component-name>`.

For the local cluster, the usual result is `in-cluster-<component-name>`.

Use these deletion controls during the migration:

```yaml
spec:
  syncPolicy:
    applicationsSync: create-update
    preserveResourcesOnDeletion: true
```

### `argocd/applicationsets/tenant-addons/`

This directory contains shared platform add-ons for tenant clusters.

Tenant add-on selectors must use explicit fleet labels. The selectors must exclude the management cluster.

The current Cilium selector requires these labels:

```yaml
fleet.fondevilla.io/role: tenant
fleet.fondevilla.io/cni: cilium
```

Install Cilium before higher-level tenant add-ons.

### `argocd/applicationsets/tenant-workloads/`

This directory contains optional workload ApplicationSets for tenant clusters.

The current workload selector requires these labels:

```yaml
fleet.fondevilla.io/role: tenant
fleet.fondevilla.io/workloads: enabled
```

Tenant workload sources use this pattern:

```text
k8s/apps/workloads/*/overlays/tenant
```

Do not select all registered clusters without a role label.

## `apps/`: deployable components

The `apps/` directory contains the Kubernetes resources that Argo CD deploys.

Each component belongs to one of these classes:

| Class | Path | Purpose |
| --- | --- | --- |
| Platform | `apps/platform/<component>/` | Cluster controllers and shared capabilities |
| Workload | `apps/workloads/<component>/` | Services that users consume |

The class describes the resource purpose. The target cluster does not determine the class.

A workload on the management cluster still belongs in `apps/workloads/`.

A platform controller for tenant clusters still belongs in `apps/platform/`.

### Platform component examples

These components belong in `apps/platform/`:

- Argo CD
- cert-manager
- Cilium
- External Secrets Operator
- 1Password Connect
- Node Feature Discovery
- KubeVirt and CDI
- Cluster API and CAPK
- Kamaji and its Cluster API provider
- KRO
- storage operators and storage classes
- Tinkerbell
- Prometheus, Loki, and Alloy

### Workload component examples

These components belong in `apps/workloads/`:

- Actual Budget
- Home Assistant
- Mosquitto
- Zigbee2MQTT
- LibreNMS
- Zot
- user-facing web services

## Standard component structure

Use this structure for each new component:

```text
<component>/
├── README.md
├── base/
│   ├── kustomization.yaml
│   └── <shared-resources>.yaml
└── overlays/
    ├── management/
    │   ├── kustomization.yaml
    │   └── <management-resources>.yaml
    └── tenant/
        ├── kustomization.yaml
        └── <tenant-resources>.yaml
```

Create only the overlays that the component supports.

Use `base/`, not `bases/`.

Use `management/`, not `control-plane/`, for the management-cluster role.

Use `tenant/`, not `workload/`, for the tenant-cluster role.

Use a lowercase, hyphen-separated component name.

Examples include `external-secrets-operator`, `node-feature-discovery`, and `local-provisioner`.

### Component README

Each component README must contain this information:

- The component purpose.
- The component class.
- The supported overlays.
- The namespace owner.
- The source type and version.
- The required dependencies.
- The secret references.
- The persistent-resource behavior.
- The render commands.
- The removal or rollback constraints.

### Base rules

The `base/` directory contains resources that all supported roles share.

The base can contain these resources:

- Namespace
- ServiceAccount and RBAC
- ConfigMap
- Service
- controller-independent custom resources
- shared labels and annotations

Do not put a cluster address, physical IP, node name, or role-specific value in the base.

Do not put an Argo CD Application in the base.

If the base resources can operate independently, make the base renderable through `base/kustomization.yaml`.

### Overlay rules

An overlay selects the base and adds values for one cluster role.

Use an overlay for these values:

- ingress hosts
- LoadBalancer addresses
- storage classes
- node selectors
- topology rules
- cluster API endpoints
- role-specific Helm values
- role-specific resource patches

Each deployable overlay must contain `kustomization.yaml` at its source root.

Argo CD must point to the overlay directory, not to a child manifest.

### Kustomize composition rules

Keep each component self-contained.

A component Kustomization must not load a file from another component through a relative parent path.

If a Kustomization loads a remote resource, use a stable remote tag or commit.

Do not require `--load-restrictor LoadRestrictionsNone` for a normal render.

Use `resources` for complete resources. Use `patches` for changes to resources that another layer owns.

Keep patches small and role-specific. Do not copy a complete upstream resource only to change one field.

If a CRD has an independent lifecycle, put that CRD in a separate platform component.

Prometheus CRDs use this pattern because the CRD lifecycle differs from the Prometheus stack lifecycle.

### Resource ownership rules

One active Argo CD Application must own each Kubernetes resource.

If dependencies, synchronization order, or removal behavior differ, split the components.

Use one Application for each component that can synchronize and roll back independently.

Do not use two active overlays to manage the same object.

If Argo CD reports a shared-resource warning, stop and correct the ownership conflict.

### YAML file rules

Use `.yaml` for new Kubernetes files.

If a safe migration requires an existing `.yml` name, keep that name.

Use one clear purpose for each file. Name the file after its main Kubernetes resource.

Examples include `namespace.yaml`, `service.yaml`, `external-secret.yaml`, and `values.yaml`.

Keep `kustomization.yaml` at every deployable Kustomize source root.

If the resources form one practical unit, you can use YAML document separators.

### Minimal component example

The base Kustomization can use this form:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: example

resources:
  - namespace.yaml
  - deployment.yaml
  - service.yaml
```

The management overlay can use this form:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base
```

## Helm sources

Pin each Helm chart to an exact version.

Do not use a floating chart version or an unqualified latest image tag.

Keep the Helm values in the overlay that consumes them.

If a Kustomization contains `helmCharts`, use `--enable-helm`.

Example:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

helmCharts:
  - name: example
    repo: https://charts.example.invalid
    version: 1.2.3
    releaseName: example
    namespace: example
    valuesFile: values.yaml
```

If the repository stores a chart copy, keep it below the component that consumes it.

Document the chart source and update method in the component README.

Do not keep a generated manifest and a Helm render active for the same resource set.

## Namespaces and resource names

Define a namespace in one clear owner component.

Set the namespace in the Kustomization or in each namespaced resource.

Use stable Kubernetes resource names. A source-path migration must not rename live resources.

Use Kubernetes recommended labels where they add clear ownership:

```yaml
app.kubernetes.io/name: <component>
app.kubernetes.io/instance: <instance>
app.kubernetes.io/part-of: <system>
```

Do not change selectors only to normalize labels. A selector change can replace workloads.

## `fleet/`: tenant lifecycle

The `fleet/` directory contains the API and policy for CAPI-managed tenant clusters.

It does not contain platform controller installation resources.

### `fleet/classes/`

This directory contains reusable tenant APIs.

The current class is the `KamajiKubevirtCluster` KRO `ResourceGraphDefinition`.

A class defines reusable topology and generated Cluster API resources. It does not contain a tenant instance.

### `fleet/profiles/`

This directory contains named capability and lifecycle profiles.

The `ephemeral/` profile records required labels, bootstrap add-ons, limits, and expiry behavior.

Keep reusable bootstrap data under the profile that owns it.

Do not put a generated kubeconfig in a profile.

### `fleet/claims/persistent/`

This directory contains intentional, long-lived tenant claims.

Each claim must identify its owner and purpose. Each claim must use explicit network and resource values.

Do not commit a short-lived request as a persistent claim.

### `fleet/examples/`

This directory contains examples and experiments that Argo CD does not reconcile.

Keep this directory outside every Git directory generator.

Do not store credentials, live claims, or generated kubeconfigs in an example.

## Tenant request contract

Each tenant request must contain these values:

- owner
- purpose
- creation time
- expiry time or maximum lifetime
- profile
- Kubernetes version
- resource size
- pod CIDR
- service CIDR

Reject an ephemeral request without ownership or expiry data.

Use these labels on an Argo CD cluster Secret:

```yaml
fleet.fondevilla.io/role: tenant
fleet.fondevilla.io/profile: ephemeral
fleet.fondevilla.io/cni: cilium
fleet.fondevilla.io/owner: victor
```

If the tenant can receive user workloads, add `fleet.fondevilla.io/workloads: enabled`.

## Tenant dependency order

Create tenant resources in this order:

1. Create the KRO claim or Cluster API resources.
2. Wait for the Kamaji control plane.
3. Wait for the CAPK KubeVirt worker virtual machines.
4. Install Cilium and required bootstrap add-ons.
5. Wait for the nodes and Cilium.
6. Register the cluster in Argo CD.
7. Add the required fleet labels.
8. Enable tenant add-on ApplicationSets.
9. Enable tenant workload ApplicationSets.

Remove tenant resources in the reverse ownership order.

Remove Argo CD registration before you remove the API endpoint.

## Network rules

Cilium is the primary CNI for management and tenant clusters.

Do not deploy Kube-OVN or Multus as a second primary CNI.

Use Kube-OVN or Multus only through an explicit Cilium chain profile.

Document these details for each chained CNI:

- interface ownership
- IPAM ownership
- route ownership
- cleanup ownership

Use an explicit profile name, such as `cilium-multus` or `cilium-kube-ovn`.

Do not use a generic tenant selector for an optional chained CNI.

## Secret and credential rules

Commit only these secret forms:

- an `ExternalSecret` or another secret reference
- encrypted data that the repository workflow supports
- a public encryption recipient
- a non-sensitive example with placeholder values

Do not commit these files or values:

- generated kubeconfigs
- age private keys
- cloud credentials
- registry passwords
- 1Password Connect credentials
- unencrypted Kubernetes Secret data
- temporary tokens

Store generated credentials outside the repository.

If another system received a committed credential, rotate that credential.

Use this command before each commit:

```sh
git ls-files | rg '(kubeconfig|credentials|age-key|secret)'
```

Review every match. A filename match is not proof that the file contains a secret.

## Storage rules

Document the owner and reclaim policy for every persistent volume.

Preserve the name and identity of a live PVC during a path migration.

If automatic storage removal can cause unacceptable data loss, use `Retain`.

Do not move a storage component until you record its bound volumes and consumers.

Do not change a storage class and a source path in the same change.

## Dependency order for management components

Use this order for a new management-cluster installation:

| Tier | Components |
| --- | --- |
| Bootstrap | Argo CD root |
| Foundation | cert-manager, secret controllers, Node Feature Discovery |
| Virtualization | KubeVirt and CDI |
| Cluster API | CAPI core, bootstrap provider, control-plane provider, CAPK |
| Hosted API | Kamaji runtime and datastore |
| Kamaji provider | Cluster API provider for Kamaji |
| Abstraction | KRO |
| Fleet class | `KamajiKubevirtCluster` |
| Instances | Persistent and ephemeral tenant claims |

Do not create tenant instances before all earlier tiers are ready.

## How to add a platform component

1. Create `apps/platform/<component>/README.md`.
2. Create `apps/platform/<component>/base/kustomization.yaml`.
3. Add shared resources to the base.
4. Create only the required role overlays.
5. Add pinned Helm values or role-specific patches to each overlay.
6. Render each overlay locally.
7. Add the required Argo CD orchestration resource.
8. Render the Argo CD root.
9. Review the Argo CD diff without pruning.
10. Update the component README with its final source path.

## How to add a workload component

1. Create `apps/workloads/<component>/README.md`.
2. Create `apps/workloads/<component>/base/kustomization.yaml`.
3. Add the workload resources to the base.
4. If the management cluster hosts the workload, add a `management` overlay.
5. If tenant clusters can host the workload, add a `tenant` overlay.
6. Render each overlay locally.
7. Add explicit selection labels for optional tenant deployment.
8. Add the required Argo CD orchestration resource.
9. Review the Argo CD diff without pruning.

## How to add an Argo CD resource

1. Put a management Application in `argocd/applications/management/`.
2. Put a management ApplicationSet in `argocd/applicationsets/management/`.
3. Put a tenant add-on ApplicationSet in `argocd/applicationsets/tenant-addons/`.
4. Put a tenant workload ApplicationSet in `argocd/applicationsets/tenant-workloads/`.
5. Add the file to the nearest `kustomization.yaml`.
6. Add that Kustomization to `argocd/kustomization.yaml` only after a live review.
7. Preserve existing Application names during migrations.
8. Use `preserveResourcesOnDeletion: true` during ownership changes.

CAUTION: When the root includes a file under `argocd/`, that file becomes active. Review its generated Applications before activation.

## Render and validation commands

Render a plain Kustomize overlay:

```sh
kustomize build k8s/apps/<class>/<component>/overlays/<role>
```

Render a Helm-enabled overlay:

```sh
kustomize build --enable-helm k8s/apps/<class>/<component>/overlays/<role>
```

Validate a render with `kubeconform`:

```sh
kustomize build --enable-helm k8s/apps/<class>/<component>/overlays/<role> \
  | kubeconform -strict -summary
```

Render the Argo CD root:

```sh
kustomize build --enable-helm k8s/argocd
```

Make sure that a directory has no incoming reference before you remove it:

```sh
rg -n 'k8s/<path>' . --glob '!graphify-out/**'
```

Make sure that Git tracks the intended files:

```sh
git status --short -- k8s/
git ls-files -- k8s/
```

### Validation requirements

If all applicable statements are true, the component change is ready:

- Every changed Kustomization renders.
- Every Helm chart uses an exact version.
- `kubeconform` reports no unexpected schema errors.
- Every Argo CD source path exists.
- Every Argo CD source path contains a supported manifest source.
- Tenant selectors exclude the management cluster.
- No plaintext credential enters the diff.
- `git diff --check` reports no whitespace error.

## Safe source-path migration

Move one live component at a time.

Do not upgrade a component during its source-path migration.

Use this sequence:

1. Copy the component to its normalized path.
2. Render the old source and the new source.
3. Make sure that both renders contain equal resources.
4. Exclude the old path from its ApplicationSet generator.
5. Add the new path to the same generator.
6. Make sure that the generated Application name stays equal.
7. Publish the staging commit.
8. Record live Application, workload, and storage identities.
9. Pause automated synchronization for the component.
10. Synchronize the manual root without pruning.
11. Make sure that the Application UID stays equal.
12. Make sure that Argo CD uses the new source path.
13. Refresh the Application.
14. Review all drift.
15. Synchronize the component without pruning.
16. Make sure that workload and storage identities stay equal.
17. Restore the previous synchronization policy.
18. Observe two clean Argo CD synchronization cycles.
19. Remove the old path in a cleanup-only commit.
20. Synchronize only the manual root without pruning.

If Argo CD shows an unexpected prune, replacement, or shared-resource warning, stop the migration.

## Legacy paths during the migration

The repository still contains paths that do not match this standard.

Some live Applications still use those paths. Do not normalize them through an unreviewed rename.

Legacy patterns include these paths:

- `1-control-plane/`
- `1-workload-cluster/`
- `apps/<component>/`
- `apps/<application>.yaml`
- `cloud-underlay/`
- top-level component directories such as `velero/`

Do not add a new component to a legacy path.

Do not use a legacy path as the example for a new component.

If all these conditions are true, remove a legacy path:

1. No live Argo CD Application uses the path.
2. No repository resource has an incoming reference to the path.
3. The normalized path contains equal resources.
4. The normalized Application is Healthy and Synced.
5. Two clean Argo CD synchronization cycles are complete.
6. The removal has a dedicated cleanup commit.

The `cloud-underlay/` directory is a temporary management bootstrap surface.

Move its resources to `apps/platform/`, `apps/workloads/`, and `argocd/` one component at a time.

### Current path disposition

When you examine a top-level directory, use this table:

| Current path type | Expected action |
| --- | --- |
| `bootstrap/`, `argocd/`, `apps/platform/`, `apps/workloads/`, `fleet/` | Keep and extend according to this document. |
| `1-control-plane/`, `1-workload-cluster/` | Migrate one live component at a time, then remove. |
| `apps/<component>/` | Move to `apps/platform/` or `apps/workloads/`. |
| `apps/<name>.yaml` | Move the wrapper to `argocd/`, then remove the old file. |
| `cloud-underlay/` | Split resources between `argocd/`, `apps/platform/`, and `apps/workloads/`. |
| Other top-level component directories | Classify, migrate to `apps/`, then remove the old root. |
| Generated tool output | Keep outside `k8s/` or add it to an applicable ignore rule. |

An existing path is not automatically approved because the path is present.

Read its live Argo source and repository references before you change it.

## Repository automation

Put repository workflows under the root `.github/workflows/` directory.

Do not create a second `.github/` directory under `k8s/`.

Keep generated renders out of Git unless a documented workflow owns those files.

If a workflow generates manifests, document the source file and generated destination.

Do not edit a generated manifest without changing its source.

## Do not add these patterns

Do not add any of these structures:

```text
k8s/<new-component>/
k8s/apps/<new-component>/
k8s/apps/<new-component>.yaml
k8s/apps/<domain>/<component>/bases/
k8s/apps/<domain>/<component>/overlays/control-plane/
k8s/apps/<domain>/<component>/overlays/workload/
```

Do not add these ownership patterns:

- an Argo CD Application inside a component directory
- component resources inside `argocd/`
- normal workloads inside `bootstrap/`
- tenant claims inside `apps/`
- platform controller installation inside `fleet/`
- examples inside an ApplicationSet directory pattern
- two active sources for the same Kubernetes resource

## Directory review checklist

Use this list for each pull request that changes `k8s/`:

- [ ] The component has one class: platform or workload.
- [ ] The component uses `base/`.
- [ ] The component uses only required role overlays.
- [ ] Each deployable overlay has `kustomization.yaml`.
- [ ] Each Helm chart has an exact version.
- [ ] The Argo CD wrapper is under `argocd/`.
- [ ] The Argo CD destination is explicit.
- [ ] The Application name is stable.
- [ ] Tenant selection uses explicit fleet labels.
- [ ] The management cluster cannot match a tenant selector.
- [ ] No generated credential is present.
- [ ] Persistent resources have documented ownership.
- [ ] All changed overlays render.
- [ ] The Argo CD root renders.
- [ ] The live diff contains no unexpected prune.
- [ ] The reorganization plan records a live path migration.

## Related documentation

- [Reorganization plan](REORGANIZATION_PLAN.md)
- [Argo CD bootstrap](bootstrap/argocd/README.md)
- [Management Applications](argocd/applications/management/README.md)
- [Tenant add-ons](argocd/applicationsets/tenant-addons/README.md)
- [Tenant workloads](argocd/applicationsets/tenant-workloads/README.md)
- [Platform components](apps/platform/README.md)
- [Workload components](apps/workloads/README.md)
- [Cloud-underlay migration](cloud-underlay/README.md)
- [Persistent tenant claims](fleet/claims/persistent/README.md)
- [Ephemeral tenant profile](fleet/profiles/ephemeral/README.md)
- [Fleet examples](fleet/examples/README.md)

This README defines the target structure. The reorganization plan controls each live migration to that structure.

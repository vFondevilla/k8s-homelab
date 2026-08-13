# Kubernetes repository structure

This directory contains Kubernetes resources for the management cluster, tenant clusters, and the VPS cluster.

The structure separates deployable components, Argo orchestration, bootstrap resources, and fleet lifecycle resources.

## Directory map

```text
k8s/
├── README.md
├── REORGANIZATION_PLAN.md
├── apps/
│   ├── platform/
│   │   └── <component>/
│   └── workloads/
│       └── <component>/
├── argocd/
│   ├── applications/
│   │   └── management/
│   ├── applicationsets/
│   │   ├── management/
│   │   ├── tenant-addons/
│   │   └── tenant-workloads/
│   └── projects/
├── bootstrap/
│   └── argocd/
└── fleet/
    ├── claims/
    ├── classes/
    ├── examples/
    └── profiles/
```

Do not create a second application root under `k8s/`.

## Component ownership

Use `apps/platform/` for cluster controllers and shared cluster capabilities.

Examples include Cilium, cert-manager, Cluster API, KubeVirt, storage controllers, and observability agents.

Use `apps/workloads/` for user services.

Examples include Actual Budget, Home Assistant, LibreNMS, n8n, and Zot.

Argo resources do not belong inside component directories. Store them under `argocd/`.

## Component contract

Each component has one base and one or more overlays:

```text
<component>/
├── README.md
├── base/
│   └── kustomization.yaml
└── overlays/
    └── <role>/
        └── kustomization.yaml
```

The base contains resources that are equal for all selected roles.

An overlay selects the base and adds role-specific values, patches, or resources.

Supported role names are:

- `management` for the existing homelab management cluster.
- `tenant` for CAPI-managed tenant clusters.
- `vps` for the separate VPS Kubernetes cluster.

Do not add an empty overlay. Add an overlay only when a deployment path selects it.

## Kustomize and Helm

Plain resources belong in a Kustomization `resources` list.

Helm components use the Kustomize `helmCharts` field in their role overlay.

Keep chart values next to the overlay Kustomization.

Do not commit downloaded chart caches. The repository ignores every generated `charts/` directory.

Do not commit generated Helm output unless a documented process owns that output.

## Argo topology

The manual bootstrap Application is `argocd`.

Its source is `k8s/argocd`.

The active Argo Kustomization includes only the management ApplicationSet.

The management ApplicationSet discovers explicit normalized component overlays.

It preserves the existing `in-cluster-<component>` Application names.

The staged management wrappers are under `argocd/applications/management/`.

The active root does not include those wrappers.

The staged tenant ApplicationSets are under these paths:

- `argocd/applicationsets/tenant-addons/`
- `argocd/applicationsets/tenant-workloads/`

The active root does not include the tenant ApplicationSets or the tenant AppProject.

## Tenant selector contract

Tenant cluster Secrets use these labels:

- `type=tenant`
- `fleet.fondevilla.io/role=tenant`
- `fleet.fondevilla.io/profile=<profile>`
- `fleet.fondevilla.io/cni=cilium`
- `fleet.fondevilla.io/workloads=enabled` when workload discovery is permitted.

Tenant selectors require the `type` label and reject `type=control-plane`.

The management cluster uses `type=control-plane`. It does not use tenant role labels.

## Fleet ownership

Use `fleet/classes/` for reusable lifecycle APIs.

Use `fleet/claims/persistent/` only for intentionally long-lived Git-managed claims.

Use `fleet/profiles/` for policy and bootstrap contracts.

Use `fleet/examples/` for non-reconciled experiments and reference manifests.

Argo discovery must not include `fleet/examples/`.

Do not store generated kubeconfigs or bootstrap Secrets in the fleet directories.

## Bootstrap ownership

The `bootstrap/` directory contains only the resources that establish the Argo root.

Normal component resources do not belong in this directory.

Apply bootstrap resources manually and review all generated Argo changes before a sync.

## Secret rules

Do not commit plaintext credentials, private keys, kubeconfigs, or generated Talos machine files.

Use External Secrets for runtime credentials when the target cluster supports it.

Encrypted files must use an approved repository encryption method.

Public keys can remain in Git only when their purpose is clear.

Search Git history before you classify an exposed credential as uncommitted.

If another system used an exposed credential, rotate it.

## Render commands

Render a plain overlay:

```sh
kustomize build k8s/apps/<area>/<component>/overlays/<role>
```

Render a Helm overlay:

```sh
kustomize build --enable-helm k8s/apps/<area>/<component>/overlays/<role>
```

Render the active Argo root:

```sh
kustomize build k8s/argocd
```

Render each staged tenant group separately:

```sh
kustomize build k8s/argocd/applicationsets/tenant-addons
kustomize build k8s/argocd/applicationsets/tenant-workloads
kustomize build k8s/argocd/projects
```

Remove generated chart caches after local validation.

## Add a component

1. Classify the component as `platform` or `workloads`.
2. Create its `README.md`.
3. Create one base Kustomization.
4. Add only the required role overlays.
5. Render every new overlay.
6. Add a staged Argo wrapper only when ApplicationSet discovery is not applicable.
7. Compare the desired resources with live resources before activation.
8. Keep automated pruning disabled during an ownership change.
9. Make sure that workload and storage identities stay equal.
10. Remove the old path in a separate cleanup commit.

## Move a live component

Record these values before you change a source path:

- Application name and UID.
- Source path and destination.
- Workload names and UIDs.
- PersistentVolume and PersistentVolumeClaim names and UIDs.
- Reclaim policies and binding states.
- Current sync policy.

Then use this sequence:

1. Render the old path.
2. Render the new path.
3. Compare both resource sets.
4. Pause automated pruning.
5. Change only the source path.
6. Refresh the Application.
7. Review every proposed prune and replacement.
8. Sync without pruning.
9. Make sure that the recorded identities remain equal.
10. Restore the approved sync policy.

If Argo reports an unexpected prune, replacement, or shared resource, stop the migration.

## Generated and local files

Keep these files outside Git:

- `graphify-out/`
- downloaded Helm `charts/`
- generated kubeconfigs
- local age private keys
- local editor configuration
- generated Talos machine files

Repository workflows belong under the root `.github/workflows/` directory.

Do not create `k8s/.github/`.

## Current state

The repository reorganization is complete.

Git tracks no numbered cluster roots, top-level component roots, or `cloud-underlay` deployment root.

Active management Applications use normalized paths under `apps/platform/` or `apps/workloads/`.

Staged components and tenant automation remain outside the active Argo root until their operational reviews are complete.

Read [REORGANIZATION_PLAN.md](REORGANIZATION_PLAN.md) for the migration record and remaining operational work.

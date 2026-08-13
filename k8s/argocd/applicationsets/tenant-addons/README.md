# Tenant add-ons ApplicationSets

This directory owns ApplicationSets for shared tenant-cluster capabilities.

Selectors use the fleet label contract. They explicitly exclude the management cluster.

The Cilium ApplicationSet is staged. The active Argo root does not include it.

The tenant Cilium overlay still contains a fixed API endpoint. Do not activate the ApplicationSet until the endpoint is dynamic.

Kube-OVN and Multus are intentionally absent until an explicit Cilium chaining
profile is implemented and validated.

The tenant selector requires these labels:

- `type=tenant`
- `fleet.fondevilla.io/role=tenant`
- `fleet.fondevilla.io/cni=cilium`

The selector requires the `type` label and rejects `type=control-plane`.

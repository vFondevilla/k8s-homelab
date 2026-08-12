# Tenant add-ons ApplicationSets

This directory owns ApplicationSets for shared tenant-cluster capabilities.
Selectors must use the fleet label contract and must explicitly exclude the
management cluster.

Tenant clusters must be reachable and have a healthy Cilium installation
before these add-ons are selected.

Kube-OVN and Multus are intentionally absent until an explicit Cilium chaining
profile is implemented and validated.

The initial tenant selector requires `fleet.fondevilla.io/role=tenant` and
`fleet.fondevilla.io/cni=cilium`.

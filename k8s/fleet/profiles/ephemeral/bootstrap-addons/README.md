# Ephemeral bootstrap add-ons

The bootstrap phase installs only the resources that make a tenant cluster reachable and schedulable.

Cilium is the primary CNI. Cilium must become healthy before Argo registers the tenant cluster.

## Endpoint constraint

The tenant Cilium values contain a fixed API endpoint. This value cannot support dynamic Kamaji tenant endpoints.

A `ClusterResourceSet` cannot replace values for each selected cluster. Therefore, do not activate the staged Cilium ApplicationSet.

The bootstrap implementation must receive the endpoint from the generated CAPI Cluster.

## Higher-level resources

Argo can install secrets, metrics, policy, storage, observability, and workloads after the tenant cluster becomes reachable.

The tenant ApplicationSets remain outside the active Argo root until the endpoint constraint is removed.

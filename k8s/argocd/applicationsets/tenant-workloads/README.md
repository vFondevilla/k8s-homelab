# Tenant workloads ApplicationSets

This directory owns optional workload ApplicationSets for tenant clusters.

The workload selector requires `type=tenant` and explicit fleet labels.

It rejects `type=control-plane`.

Generated Application names include the tenant cluster name and workload component name.

The active Argo root does not include this staged ApplicationSet.

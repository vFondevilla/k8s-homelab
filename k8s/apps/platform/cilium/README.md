# Cilium

Cilium is the primary CNI for management and tenant clusters.

This component is a platform network component.

## Overlays

The management overlay is `overlays/management/`.

The tenant overlay is `overlays/tenant/`. It is a reusable starting point and needs tenant-specific API values.

Kube-OVN and Multus are not alternative primary CNIs. Use them only in an explicit Cilium chain.

## Dependencies

The management overlay defines BGP peering and LoadBalancer address pools.

The Cilium Helm chart creates two certificate Secrets during each render. Their generated values are not deterministic.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/cilium/overlays/management
```

## Migration constraint

Preserve the `in-cluster-cilium` Application name.

Keep automated sync disabled during the source-path migration. Do not replace the live Cilium certificate Secrets.

Compare all non-Secret resources before a path switch. Review BGP and address-pool drift separately.

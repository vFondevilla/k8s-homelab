# Prometheus

Prometheus and Grafana provide monitoring for the management cluster.

This component is a platform observability component.

## Overlay

The management overlay is `overlays/management/`.

The overlay installs the kube-prometheus-stack chart in the `prometheus` namespace.

## Dependencies

The chart needs the Prometheus Operator CRDs. The separate Prometheus CRD component manages those CRDs.

The ingress uses the Cilium ingress class and the `letsencrypt-prod` ClusterIssuer.

## Persistent resources

Grafana uses the static `grafana-pv` volume. Prometheus uses the static `prometheus-pv` volume.

Both PV reclaim policies are `Retain`. Preserve all PV and PVC identities during a source-path migration.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/prometheus/overlays/management
```

## Migration constraint

Preserve the `in-cluster-prometheus` Application name.

Do not switch the source while an old sync operation is active. Synchronize the component without pruning after the operation ends.

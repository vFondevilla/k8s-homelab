# Prometheus SNMP Exporter

The Prometheus SNMP Exporter collects metrics from network devices.

This component is not active in Argo CD.

## Overlay

The management overlay is `overlays/management/`.

The overlay installs chart `6.0.0` in the `prom` namespace.

The configuration creates ServiceMonitor targets for the storage router, UniFi core switch, and UniFi router.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/prometheus-snmp-exporter/overlays/management
```

Do not add this component to Argo discovery until the SNMP authentication configuration is complete.

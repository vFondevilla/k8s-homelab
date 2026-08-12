# Alloy

Alloy collects pod logs from the management cluster. It sends the logs to the Loki service.

This component is a platform observability component.

## Source

The management overlay uses the Grafana Alloy Helm chart at version `0.12.0`.

Kustomize gets the chart from `https://grafana.github.io/helm-charts` during the render.

The repository ignore rules exclude the local Helm chart cache.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `alloy` namespace. It uses a DaemonSet on the management cluster.

## Dependencies

The Alloy configuration sends logs to `http://loki.loki.svc.cluster.local:3100`.

Loki must accept log traffic at this address.

## Persistent resources

This component has no persistent volume.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/alloy/overlays/management
```

## Migration constraint

Preserve the `in-cluster-alloy` Application name during a source-path migration.

Preserve the DaemonSet and pod identities when the rendered resources do not change.

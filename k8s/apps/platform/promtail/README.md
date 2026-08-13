# Promtail

Promtail collects Kubernetes logs from each management-cluster node. It sends these logs to Loki.

This component is a platform observability component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `promtail` namespace. It also creates cluster-wide read permissions.

## Dependencies

Promtail sends logs to the Loki gateway at `loki-gateway.loki.svc.cluster.local`.

The DaemonSet mounts the node log directories. It also stores positions in a node-local directory.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/platform/promtail/overlays/management
```

## Migration constraint

Preserve the `in-cluster-promtail` Application name.

Preserve the DaemonSet and pod UIDs during a source-path migration.

The DaemonSet can stay Progressing while unavailable nodes still have scheduled pods.

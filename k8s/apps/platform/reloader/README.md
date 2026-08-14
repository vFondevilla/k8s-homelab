# Reloader

Stakater Reloader watches ConfigMaps and Secrets and triggers rolling updates
for workloads that opt in with annotations.

The management overlay installs chart version `2.2.16` with application
version `v1.4.21` in the `reloader` namespace. It watches all namespaces but
does not reload every workload automatically.

Reloader uses the `annotations` reload strategy to integrate with Argo CD.
Annotate a workload for automatic discovery of referenced resources:

```yaml
metadata:
  annotations:
    reloader.stakater.com/auto: "true"
```

Use `configmap.reloader.stakater.com/auto: "true"` or
`secret.reloader.stakater.com/auto: "true"` to limit the watched resource
type. Jobs and CronJobs are excluded by the management configuration.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/reloader/overlays/management
```

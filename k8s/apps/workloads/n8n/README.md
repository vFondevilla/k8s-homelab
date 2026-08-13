# n8n

n8n provides workflow automation on the VPS Kubernetes cluster.

Ansible applies this component directly. Argo CD does not discover the VPS overlay.

## Structure

The `base/` directory contains the namespace, workloads, services, storage, IngressRoute, and ExternalSecret.

The `overlays/vps/` directory selects the base for the `vps-cluster` context.

## Storage

The PersistentVolume uses `/opt/k8s-data/n8n` on the VPS host. Its reclaim policy is `Retain`.

The workload also mounts `/opt/k8s-data/n8n-files` from the VPS host.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/workloads/n8n/overlays/vps
```

The migration playbook uses the same overlay path.

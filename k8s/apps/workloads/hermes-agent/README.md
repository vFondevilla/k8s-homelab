# Hermes Agent VM

The management overlay manages the existing Hermes VM in the `kubevirt` namespace.
It includes the VM, root DataVolume, LoadBalancer Service, and SSH public-key Secret.

## Argo CD

The management ApplicationSet discovers `overlays/management` and creates `in-cluster-hermes-agent`.
Automatic sync and self-healing are enabled. Automatic pruning is disabled for this stateful workload.
The DataVolume also has `Prune=false,Delete=false` to preserve its disk when Argo removes resources or deletes an Application.

KubeVirt manages the running VirtualMachineInstance. CDI manages the root PersistentVolumeClaim.
The manifests retain the existing resource names, namespace, disk source, and MAC address.

## Render and validate

From the repository root:

```sh
kustomize build k8s/apps/workloads/hermes-agent/overlays/management
kubectl --context homelab apply --dry-run=server -k k8s/apps/workloads/hermes-agent/overlays/management
```

## Access and storage

- SSH: `ubuntu@hermes.fondevilla.io`
- VM: `kubevirt/hermes-agent`
- Root disk: `kubevirt/hermes-agent-rootdisk`, on `nfs-client`
- Public keys: `kubevirt/hermes-agent-ssh`, synchronized through the QEMU guest agent
- Hindsight database: [separate CNPG component](../hindsight/README.md)

Changes to the VM template can require a restart. Argo synchronization does not perform that restart.

Reference: [Argo CD resource retention](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/).

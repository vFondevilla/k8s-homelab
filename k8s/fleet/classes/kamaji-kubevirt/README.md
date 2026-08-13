# Kamaji KubeVirt Fleet Class

This directory contains the reusable API definition for tenant clusters.

The class uses Kamaji control planes and CAPK KubeVirt workers.

Claims and generated kubeconfig files do not belong in this directory.

## Request example

```yaml
apiVersion: homelab.fondevilla.io/v1alpha1
kind: KamajiKubevirtCluster
metadata:
  name: example
  namespace: default
spec:
  version: v1.30.1
  profile: ephemeral
  networkProfile: cilium
  workerReplicas: 1
```

The resource graph creates the tenant namespace and the required Cluster API resources.

These resources include the Cluster, control plane, bootstrap template, machine template, and worker MachineDeployment.

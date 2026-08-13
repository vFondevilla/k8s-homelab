# Cluster API + KubeVirt PoC (Ubuntu 24.04)

This PoC creates a Kubernetes workload cluster on **KubeVirt** using **Ubuntu 24.04** VMs and the **kubeadm** bootstrap/control-plane providers.

Files:

- `cluster-template.yaml`: `clusterctl` template for a **single-node** (control-plane only) cluster.

## Prereqs (management cluster)

- Cluster API core installed.
- Providers installed:
  - `infrastructure-kubevirt` (CAPK)
  - `bootstrap-kubeadm` (CABPK)
  - `control-plane-kubeadm` (KCP)
- KubeVirt + CDI working.
- A default `StorageClass` (or set `STORAGE_CLASS`).
- A `LoadBalancer` implementation (e.g. MetalLB), because the API server Service uses `type: LoadBalancer` + `loadBalancerIP`.

## Prepare an Ubuntu 24.04 image

You need an HTTP-accessible disk image for CDI import.

Good starting points:

- Ubuntu cloud image (qcow2): `https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img`

Host it somewhere reachable from the management cluster (an internal webserver is easiest), then set `UBUNTU_2404_IMAGE_URL`.

## Create a cluster

From this directory:

```bash
export CLUSTER_NAME=ubuntu-2404-poc
export NAMESPACE=$CLUSTER_NAME

# Must be routable for your mgmt cluster + LB.
export CONTROL_PLANE_ENDPOINT_IP=10.253.0.50

# Where CDI will import the OS disk from (qcow2).
export UBUNTU_2404_IMAGE_URL=https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img

# Kubernetes version (used by CAPI objects)
export KUBERNETES_VERSION=v1.30.0

# Used for the pkgs.k8s.io apt repo in cloud-init
export KUBERNETES_PKG_REPO_VERSION=v1.30

# Optional tuning
export STORAGE_CLASS=nfs-client
export CONTROL_PLANE_MACHINE_COUNT=1
export WORKER_MACHINE_COUNT=0

# Default installs flannel; swap for cilium/calico/etc if you prefer.
export CNI_MANIFEST_URL=https://raw.githubusercontent.com/flannel-io/flannel/v0.25.5/Documentation/kube-flannel.yml

clusterctl generate cluster "$CLUSTER_NAME" \
  --from cluster-template.yaml \
  --target-namespace "$NAMESPACE" \
  --control-plane-machine-count "$CONTROL_PLANE_MACHINE_COUNT" \
  > "$CLUSTER_NAME.yaml"

kubectl apply -f "$CLUSTER_NAME.yaml"
```

Watch it come up:

```bash
kubectl -n "$NAMESPACE" get cluster,kubeadmcontrolplane,machinedeployment,machine

# If you have these CRDs installed:
kubectl -n "$NAMESPACE" get kubevirtmachines
```

Fetch kubeconfig:

```bash
clusterctl get kubeconfig "$CLUSTER_NAME" -n "$NAMESPACE" > "$CLUSTER_NAME.kubeconfig"
kubectl --kubeconfig "$CLUSTER_NAME.kubeconfig" get nodes -owide
```

## Notes / troubleshooting

- If machines are stuck before `kubeadm`, it’s usually:
  - No egress from the VM network to `pkgs.k8s.io` (apt repo) and/or your `CNI_MANIFEST_URL`.
  - `STORAGE_CLASS` mismatch or CDI import failures.
  - `CONTROL_PLANE_ENDPOINT_IP` not being allocated by your LoadBalancer.
- If you see `VM not bootstrapped yet` on Machines, ensure your `KubevirtMachineTemplate` includes a `cloudinitdisk` volume with `cloudInitNoCloud.userDataBase64: ""` (the infra provider fills this in from the bootstrap secret). The included template already does this.

## Adding workers later

For the demo, this template intentionally creates **no workers**.
If you want, I can add a worker `MachineDeployment` back in once the control plane is stable (it’s a few extra objects, and it’s nicer to debug in two phases).
- If you want fully offline/airgapped behavior, the easiest follow-up is:
  - mirror the apt repo + CNI manifest internally, then point `CNI_MANIFEST_URL` and the `pkgs.k8s.io` URLs at your mirror.

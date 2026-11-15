# Democratic CSI

This component contains pinned Democratic CSI configurations for TrueNAS SCALE.

- Helm chart: `0.15.1`
- Driver image: `v1.9.5`
- Management API: `https://10.1.0.3:443`
- NFS and iSCSI data endpoint: `10.254.0.3`
- iSCSI portal group: `1`
- iSCSI initiator group: `1`

The management and tenant overlays use different CSI driver identities.

They also use different instance IDs, parent datasets, and iSCSI target prefixes.

Neither StorageClass is the default StorageClass.

Snapshot sidecars and classes remain disabled until the cluster contains the snapshot controller and CRDs.

The configuration uses HTTPS with `allowInsecure: true` as an explicit homelab exception. Certificate verification remains a separate task.

Talos `v1.11.0` with `iscsi-tools v0.2.0` uses `/usr/local/sbin/iscsiadm`.

Talos does not expose `/usr/local/etc/iscsi` to kubelet.

The chart uses `/var/iscsi` as its writable iSCSI directory. Its hostPath type is `DirectoryOrCreate`.

Render an overlay with:

```sh
kustomize build --enable-helm k8s/apps/platform/democratic-csi/overlays/management
kustomize build --enable-helm k8s/apps/platform/democratic-csi/overlays/tenant
```

The management overlay is active through the `in-cluster-democratic-csi` Argo CD application.

## HTTP credential protection

Both overlays load `components/http-safety/http-safety.cjs` into each controller and node driver through `NODE_OPTIONS`.
The patch targets the pinned `v1.9.5` image and its internal FreeNAS HTTP client.
Check this patch before each driver upgrade. Remove it only after an upstream fix passes the same tests.

The client refuses plain HTTP before it sends credentials. Debug logs contain only the method, status, and duration.
Successful response bodies remain unchanged. Failed responses contain a status message instead of the response body.
The client removes Axios request objects, headers, and configuration from returned responses and errors.
This prevents probe errors from exposing the API key through gRPC, sidecar logs, and Kubernetes events.

`tests/http-safety.cjs` tests all four HTTP methods against a local HTTPS server in the pinned driver image.
It checks successful requests, HTTP 401 and 500 responses, probe errors, connection errors, debug logs, and rejection of plain HTTP.
The test uses a fake credential and an ephemeral TLS certificate. It makes no TrueNAS requests.

Run the test against a running CSI pod:

```sh
python3 k8s/apps/platform/democratic-csi/tests/check-http-safety.py --context homelab --pod POD_NAME
```

## Credential recovery

Both ExternalSecrets read the `password` field of `truenas democratic csi api token` in the `Lab` vault.
The Secrets refresh every hour. The driver reads its configuration at startup and needs a restart after rotation.

1. Check the TrueNAS key metadata and its revocation reason without printing the key.
2. Deploy the HTTP protection before replacing an exposed key.
3. Reset only the dedicated `democratic_csi` key through the TrueNAS local administration interface.
4. Save the replacement in 1Password through standard input. Keep the value out of command arguments, files, and terminal output.
5. Annotate both ExternalSecrets with a new `force-sync` value.
6. Check that both Kubernetes Secrets match 1Password without printing their contents.
7. Restart both controller Deployments and both node DaemonSets.
8. Check provisioning and read/write access with disposable NFS and iSCSI volumes.

On 2026-11-15, TrueNAS reported that an insecure transport attempt revoked the CSI key.
The Kubernetes Secrets matched 1Password, but HTTPS authentication returned HTTP 401.
The driver also included its authorization header in failed probe responses.
Rotation invalidates the exposed credential. Historical logs and events can still contain the old value until their retention periods expire.

The replacement key passed HTTPS authentication. The old key returned HTTP 401.
Both controllers returned to full readiness after Secret synchronization and restart.
The iSCSI test passed provisioning, an 8 MiB write, and checksum verification from a fresh pod on `node09`.

NFS provisioning passed, but the NFS mount test failed with `No such file or directory`.
The test dataset existed, and TrueNAS exported it to the configured storage addresses.
Node09 also had NFS mounts for `10.254.0.3` whose effective server address was `10.1.0.3`.
The TrueNAS export cache recorded a denied lookup for the CSI path from the management subnet.
This evidence points to NFS connection reuse through the management network, which the CSI export host list excludes.
NFS data access requires a separate correction before workload adoption.

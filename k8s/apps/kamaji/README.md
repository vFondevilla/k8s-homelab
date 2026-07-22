# Kamaji

Installs Kamaji on the control-plane cluster.

Pinned chart:

- `kamaji` chart: `1.0.0`
- Chart repository: `https://clastix.github.io/charts`

The chart deploys Kamaji and its bundled etcd datastore in `kamaji-system`.
The etcd PVC leaves `storageClassName` empty so the cluster default
`StorageClass` is used.

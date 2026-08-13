# Kube Resource Orchestrator platform component

KRO owns the `kro.run` API that the fleet classes use.

KRO is separate from the Cluster API providers. This separation makes the dependency order visible.

The order is providers, Kamaji runtime, KRO, fleet classes, and claims.

The pinned chart version follows the official installation guidance at <https://kro.run/docs/getting-started/Installation/>.

# Hindsight database for Hermes

This component creates a CloudNativePG database for Hindsight on the Hermes VM.
The management overlay uses the existing `kubevirt` namespace.
The Hindsight API and Hermes plugin are configured separately on the VM.

## Database

- Cluster: `hindsight-db`
- Database and owner: `hindsight`
- PostgreSQL: `18.4`, with the CNPG standard image pinned by digest
- Extensions: `vector`, `pg_trgm`, and `uuid-ossp` in the `public` schema
- Storage: `20Gi` on `truenas-iscsi`
- Instances: one; no standby or database backup is configured
- Endpoint: `hindsight-db-rw.kubevirt.svc.cluster.local:5432`

CNPG creates the `hindsight-db-app` Secret with generated credentials.
The application role has no superuser access.
The database uses an internal ClusterIP service, reachable from the Hermes pod network.

## Deploy

From the repository root:

```sh
kustomize build k8s/apps/workloads/hindsight/overlays/management
kubectl --context homelab apply --dry-run=server -k k8s/apps/workloads/hindsight/overlays/management
kubectl --context homelab apply -k k8s/apps/workloads/hindsight/overlays/management
kubectl --context homelab -n kubevirt wait clusters.postgresql.cnpg.io/hindsight-db --for=condition=Ready --timeout=300s
```

The management ApplicationSet discovers this overlay after these files reach `main`.

## Connect Hindsight

Set `HINDSIGHT_API_DATABASE_URL` in the environment of the Hindsight API process on Hermes.
Read its value from the `fqdn-uri` key of the `kubevirt/hindsight-db-app` Secret.
Append `?sslmode=require` to require TLS.
Set `HINDSIGHT_API_VECTOR_EXTENSION=pgvector`.

The following command retrieves the connection URI. Treat its output as a password.

```sh
kubectl --context homelab -n kubevirt get secret hindsight-db-app \
  -o jsonpath='{.data.fqdn-uri}' | base64 --decode
```

Hindsight creates its tables during startup.
Configure its LLM provider and Hermes integration separately.

References: [Hindsight configuration](https://hindsight.vectorize.io/developer/configuration),
[CNPG application connections](https://cloudnative-pg.io/docs/1.30/applications/),
and [CNPG PostgreSQL images](https://github.com/cloudnative-pg/postgres-containers).

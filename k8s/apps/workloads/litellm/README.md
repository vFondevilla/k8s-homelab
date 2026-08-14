# LiteLLM

LiteLLM provides an OpenAI-compatible AI gateway and stores its runtime state in
a CloudNativePG PostgreSQL database.

## Structure

The `base/` directory contains the namespace, LiteLLM configuration, External
Secrets, Deployment, Service, and Ingress.

The `overlays/management/` directory adds a single-instance CloudNativePG
database backed by the `truenas-iscsi` StorageClass.

The database requests one expandable 10 Gi volume. The StorageClass uses the
`Retain` reclaim policy, but that does not replace database backups.

## 1Password prerequisites

Create these items before the first Argo CD sync:

- `litellm`: custom fields `master-key` and `salt-key`. Keep `salt-key`
  permanent after LiteLLM writes encrypted data.
- `litellm-database`: login fields `username` and `password`, plus a custom
  field named `uri`.

Set the database username to `litellm`. Use this URI, substituting the
URL-encoded password:

```text
postgresql://litellm:<password>@litellm-db-rw.litellm.svc.cluster.local:5432/litellm?sslmode=require
```

Both LiteLLM keys should be long random values beginning with `sk-`.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/workloads/litellm/overlays/management
```

The management overlay is included explicitly in the control-plane
ApplicationSet. The root `argocd` Application must be synced after this change
is committed and pushed.

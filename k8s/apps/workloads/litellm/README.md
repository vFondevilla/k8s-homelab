# LiteLLM

LiteLLM provides an OpenAI-compatible AI gateway and stores its runtime state in
a CloudNativePG PostgreSQL database.

## Structure

The `base/` directory contains the namespace, LiteLLM configuration, External
Secrets, Deployment, Service, and Ingress.

The `overlays/management/` directory adds a single-instance CloudNativePG
database and a dedicated ChatGPT OAuth token volume. Both use the
`truenas-iscsi` StorageClass.

The database requests one expandable 10 Gi volume. ChatGPT OAuth requests a
separate 1 Gi volume mounted at `/var/lib/litellm/chatgpt`. The StorageClass
uses the `Retain` reclaim policy, but that does not replace backups.

## ChatGPT subscription OAuth

The proxy exposes the documented `chatgpt/*` models. The first request starts
the ChatGPT device-code flow and prints the verification URL and code in the
LiteLLM logs. Tokens and refreshed credentials are stored in
`auth.json` on the dedicated PVC.

Keep the LiteLLM Deployment at one replica. LiteLLM uses one process-wide
ChatGPT token directory and auth file, so this configuration supports one
ChatGPT subscription account.

## 1Password prerequisites

Create these items before the first Argo CD sync:

- `litellm`: custom fields `master-key` and `salt-key`. Keep `salt-key`
  permanent after LiteLLM writes encrypted data.
- `litellm-database`: login fields `username` and `password`.

Set the database username to `litellm`. External Secrets constructs the
PostgreSQL URI and URL-encodes the password.

Both LiteLLM keys should be long random values beginning with `sk-`.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/workloads/litellm/overlays/management
```

The management overlay is included explicitly in the control-plane
ApplicationSet. The root `argocd` Application must be synced after this change
is committed and pushed.

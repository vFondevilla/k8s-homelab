# 1Password Connect platform component

This component consumes credentials provisioned outside Git. Do not restore
generated `1password-credentials.json` files into the repository.

For a fresh single-cluster install, use the bootstrap helper. It treats
1Password as the source of truth, optionally verifies a local credentials file
matches the vault document, and creates the Kubernetes bootstrap Secrets
expected by 1Password Connect and ESO:

```sh
scripts/bootstrap-single-cluster-1password-connect.sh \
  --context <target-kube-context>
```

If you still have a local `1password-credentials.json`, you can verify it
matches the vault copy before bootstrapping:

```sh
scripts/bootstrap-single-cluster-1password-connect.sh \
  --context <target-kube-context> \
  --credentials-file <path-to-1password-credentials.json>
```

To create a fresh 1Password Connect server and token, only when the target
1Password items do not already exist:

```sh
scripts/bootstrap-single-cluster-1password-connect.sh \
  --context <target-kube-context> \
  --create-server
```

The management overlay exposes the Connect API at:

```text
https://onepassword-connect.cp.fondevilla.io
```

Tenant clusters should deploy only External Secrets Operator and point their
`ClusterSecretStore` at that URL. They still need the Connect token Secret
bootstrapped locally:

```sh
scripts/bootstrap-eso-1password-token.sh \
  --context <target-kube-context>
```

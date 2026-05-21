Deploy the application then create the 1password connect server in 1password:

```
op connect server create kubernetes --vaults "Lab"
kubectl create secret generic op-credentials -n 1p --from-literal=1password-credentials.json="$(cat 1password-credentials.json | base64)"
```

The control-plane overlay exposes the Connect API at:

```text
https://onepassword-connect.cp.fondevilla.io
```

Workload clusters should deploy only External Secrets Operator and point their
`ClusterSecretStore` at that URL. They still need the Connect token Secret
bootstrapped locally:

```sh
scripts/bootstrap-eso-1password-token.sh \
  --context <target-kube-context>
```

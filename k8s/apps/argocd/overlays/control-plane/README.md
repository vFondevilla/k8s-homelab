age-op -d -k op://Personal/age -o argocd-repositories.yaml.decrypt argocd-repositories.yaml.age

## Declarative cluster credentials

Argo CD discovers managed clusters from Secrets in the `argocd` namespace with the
`argocd.argoproj.io/secret-type: cluster` label. Remote cluster credentials are
created by External Secrets Operator from 1Password.

For the workload cluster, create a 1Password item in the `Lab` vault named
`argocd-cluster-workload-cluster` with these fields:

```text
server=<remote Kubernetes API URL>
bearerToken=<argocd-manager service account token>
```

The generated Argo CD Secret uses `tlsClientConfig.insecure: true`, so no cluster
CA field is required.

You can create/update that 1Password item from an admin kubeconfig context with:

```sh
scripts/register-argocd-cluster-1password.sh \
  --name workload-cluster \
  --context <target-kube-context>
```

The script creates an `argocd-manager` ServiceAccount, token Secret, and
`cluster-admin` ClusterRoleBinding in the target cluster, then stores the target
API server and bearer token in 1Password.

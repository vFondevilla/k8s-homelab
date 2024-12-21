Deploy the application then create the 1password connect server in 1password:

```
op connect server create kubernetes --vaults "Lab"
kubectl create secret generic op-credentials -n 1p --from-literal=1password-credentials.json="$(cat 1password-credentials.json | base64)"
```


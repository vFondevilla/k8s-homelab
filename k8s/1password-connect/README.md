For decryption, first export from 1password the age key:
```
export SOPS_AGE_RECIPIENTS=$(<public-age-keys.txt)
export SOPS_AGE_KEY_FILE=$(pwd)/secrets/age-key.txt
sops --decrypt --input-type json --output-type json --in-place 1password-credentials.json
```

Then install the helm chart
```
helm install connect 1password/connect --set-file connect.credentials=1password-credentials.json
```

Then encrypt again
```
sops --encrypt --age ${SOPS_AGE_RECIPIENTS} --in-place k8s/1password-connect/1password-credentials.json
```
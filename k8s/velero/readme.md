Manually create the secret for the auth

```
[minio]
aws_access_key_id = velero
aws_secret_access_key = REDACTED
```

k create secret generic velero-auth --from-file=credentials
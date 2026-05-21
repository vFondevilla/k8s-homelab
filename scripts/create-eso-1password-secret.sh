#!/usr/bin/env bash
set -euo pipefail

CREDENTIALS_ITEM="kubernetes Credentials File"
CONNECT_TOKEN_ITEM="kubernetes Access Token: Kubernetes"
VAULT="Lab"

echo "==> Creating namespaces..."
kubectl create namespace 1p --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace external-secrets --dry-run=client -o yaml | kubectl apply -f -

echo "==> Reading 1Password Connect credentials from 1Password..."
CREDENTIALS_JSON=$(op document get "${CREDENTIALS_ITEM}" --vault "${VAULT}")

if [[ -z "${CREDENTIALS_JSON}" ]]; then
  echo "Error: could not read credentials from 1Password document '${CREDENTIALS_ITEM}'" >&2
  exit 1
fi

echo "==> Creating credentials secret (1p/op-credentials)..."
CREDENTIALS_B64=$(echo -n "${CREDENTIALS_JSON}" | base64 | tr -d '\n')
kubectl create secret generic op-credentials \
  --namespace 1p \
  --from-literal=1password-credentials.json="${CREDENTIALS_B64}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Reading Connect token from 1Password..."
CONNECT_TOKEN=$(op item get "${CONNECT_TOKEN_ITEM}" --vault "${VAULT}" --fields credential --reveal)

if [[ -z "${CONNECT_TOKEN}" ]]; then
  echo "Error: could not read Connect token from 1Password item '${CONNECT_TOKEN_ITEM}'" >&2
  exit 1
fi

echo "==> Creating Connect token secret (external-secrets/onepassword-connect-token)..."
kubectl create secret generic onepassword-connect-token \
  --namespace external-secrets \
  --from-literal=token="${CONNECT_TOKEN}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Done. Secrets created:"
echo "    1p/op-credentials"
echo "    external-secrets/onepassword-connect-token"

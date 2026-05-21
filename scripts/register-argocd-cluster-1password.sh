#!/usr/bin/env bash
set -euo pipefail

VAULT="Lab"
CLUSTER_NAME=""
KUBE_CONTEXT=""
SERVER=""
ITEM_NAME=""
SERVICE_ACCOUNT="argocd-manager"
SERVICE_ACCOUNT_NAMESPACE="kube-system"
TOKEN_SECRET=""

usage() {
  printf '%s\n' \
    "Usage: $0 --name <argocd-cluster-name> --context <target-kube-context> [options]" \
    "" \
    "Creates/updates the target cluster argocd-manager ServiceAccount credentials in 1Password." \
    "" \
    "Options:" \
    "  --name <name>                 Argo CD cluster name and default 1Password item suffix" \
    "  --context <context>           kubeconfig context for the target cluster" \
    "  --server <url>                Kubernetes API URL; defaults to the context cluster server" \
    "  --item <name>                 1Password item name; defaults to argocd-cluster-<name>" \
    "  --vault <vault>               1Password vault; default: Lab" \
    "  --service-account <name>      ServiceAccount name; default: argocd-manager" \
    "  --namespace <namespace>       ServiceAccount namespace; default: kube-system" \
    "  -h, --help                    Show this help"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command not found: $1" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      CLUSTER_NAME="$2"
      shift 2
      ;;
    --context)
      KUBE_CONTEXT="$2"
      shift 2
      ;;
    --server)
      SERVER="$2"
      shift 2
      ;;
    --item)
      ITEM_NAME="$2"
      shift 2
      ;;
    --vault)
      VAULT="$2"
      shift 2
      ;;
    --service-account)
      SERVICE_ACCOUNT="$2"
      shift 2
      ;;
    --namespace)
      SERVICE_ACCOUNT_NAMESPACE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${CLUSTER_NAME}" || -z "${KUBE_CONTEXT}" ]]; then
  usage >&2
  exit 1
fi

require_cmd kubectl
require_cmd op

ITEM_NAME="${ITEM_NAME:-argocd-cluster-${CLUSTER_NAME}}"
TOKEN_SECRET="${SERVICE_ACCOUNT}-token"

if [[ -z "${SERVER}" ]]; then
  KUBE_CLUSTER="$(kubectl config view --raw -o "jsonpath={.contexts[?(@.name=='${KUBE_CONTEXT}')].context.cluster}")"
  SERVER="$(kubectl config view --raw -o "jsonpath={.clusters[?(@.name=='${KUBE_CLUSTER}')].cluster.server}")"
fi

if [[ -z "${SERVER}" ]]; then
  echo "Error: could not determine Kubernetes API server for context '${KUBE_CONTEXT}'" >&2
  exit 1
fi

echo "==> Bootstrapping Argo CD manager credentials in context '${KUBE_CONTEXT}'..."
kubectl --context "${KUBE_CONTEXT}" apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ${SERVICE_ACCOUNT}
  namespace: ${SERVICE_ACCOUNT_NAMESPACE}
---
apiVersion: v1
kind: Secret
metadata:
  name: ${TOKEN_SECRET}
  namespace: ${SERVICE_ACCOUNT_NAMESPACE}
  annotations:
    kubernetes.io/service-account.name: ${SERVICE_ACCOUNT}
type: kubernetes.io/service-account-token
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: ${SERVICE_ACCOUNT}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
  - kind: ServiceAccount
    name: ${SERVICE_ACCOUNT}
    namespace: ${SERVICE_ACCOUNT_NAMESPACE}
EOF

echo "==> Waiting for service account token..."
for _ in {1..30}; do
  TOKEN="$(kubectl --context "${KUBE_CONTEXT}" -n "${SERVICE_ACCOUNT_NAMESPACE}" get secret "${TOKEN_SECRET}" -o jsonpath='{.data.token}' 2>/dev/null || true)"
  if [[ -n "${TOKEN}" ]]; then
    break
  fi
  sleep 1
done

if [[ -z "${TOKEN:-}" ]]; then
  echo "Error: token was not populated in secret '${SERVICE_ACCOUNT_NAMESPACE}/${TOKEN_SECRET}'" >&2
  exit 1
fi

BEARER_TOKEN="$(printf '%s' "${TOKEN}" | base64 --decode)"

echo "==> Upserting 1Password item '${ITEM_NAME}' in vault '${VAULT}'..."
if op item get "${ITEM_NAME}" --vault "${VAULT}" >/dev/null 2>&1; then
  op item edit "${ITEM_NAME}" \
    --vault "${VAULT}" \
    "server=${SERVER}" \
    "bearerToken=${BEARER_TOKEN}" \
    < /dev/null
else
  op item create \
    --category "API Credential" \
    --vault "${VAULT}" \
    --title "${ITEM_NAME}" \
    "server=${SERVER}" \
    "bearerToken=${BEARER_TOKEN}" \
    < /dev/null
fi

echo "==> Done."
echo "    cluster: ${CLUSTER_NAME}"
echo "    context: ${KUBE_CONTEXT}"
echo "    server:  ${SERVER}"
echo "    item:    ${ITEM_NAME}"

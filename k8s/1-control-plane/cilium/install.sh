#!/usr/bin/env bash
set -euo pipefail

# Installs the latest Cilium Helm chart using values.yaml in this directory.
# Usage:
#   chmod +x install.sh
#   ./install.sh
#
# Optional env vars:
#   NAMESPACE       - Target namespace (default: kube-system)
#   RELEASE_NAME    - Helm release name (default: cilium)
#   CHART_VERSION   - Specific chart version (default: latest available)
#   VALUES_FILE     - Path to values file (default: values.yaml)

NAMESPACE=${NAMESPACE:-kube-system}
RELEASE_NAME=${RELEASE_NAME:-cilium}
VALUES_FILE=${VALUES_FILE:-values.yaml}
CHART_REPO=${CHART_REPO:-https://helm.cilium.io}
CHART_NAME=${CHART_NAME:-cilium/cilium}
CHART_VERSION=${CHART_VERSION:-}

if ! command -v helm >/dev/null 2>&1; then
  echo "Error: helm is not installed or not in PATH" >&2
  exit 1
fi

echo "Adding/Updating Helm repo: cilium -> ${CHART_REPO}" 
if ! helm repo list | awk '{print $1}' | grep -qx "cilium"; then
  helm repo add cilium "${CHART_REPO}"
fi
helm repo update

echo "Installing/Upgrading ${RELEASE_NAME} in namespace ${NAMESPACE} using ${VALUES_FILE}" 
cmd=(
  helm upgrade --install "${RELEASE_NAME}" "${CHART_NAME}"
  --namespace "${NAMESPACE}" --create-namespace
  -f "${VALUES_FILE}"
  --wait --timeout 15m
)

if [[ -n "${CHART_VERSION}" ]]; then
  cmd+=(--version "${CHART_VERSION}")
fi

"${cmd[@]}"

echo "Cilium installation complete."

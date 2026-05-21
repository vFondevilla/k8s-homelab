#!/usr/bin/env bash
set -euo pipefail

# Migrates Argo Application app.yaml files to helmfile + folder-only Git source
# - For each k8s/*/app.yaml that contains Helm sources, generates k8s/<app>/helmfile.yaml
# - Modifies app.yaml to keep only the folder Git source with directory.recurse: true
# - Does not commit changes

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
K8S_DIR="$ROOT_DIR/k8s"

if ! command -v yq >/dev/null 2>&1; then
  echo "yq is required (v4.x). Please install yq." >&2
  exit 1
fi

REPO_GIT_URL='git@github.com:vFondevilla/k8s-homelab.git'

slug_repo_name() {
  local url="$1"
  # strip scheme, trailing slash, then take last path segment, sanitize
  url="${url#http://}"; url="${url#https://}"
  url="${url%/}"
  local last
  last=$(echo "$url" | awk -F'/' '{print $NF}')
  echo "$last" | sed -E 's/[^A-Za-z0-9_-]+/-/g'
}

process_app() {
  local app_file="$1"
  local dir
  dir=$(dirname "$app_file")
  local app_name ns create_ns_flag
  app_name=$(yq e '.metadata.name' "$app_file")
  ns=$(yq e '.spec.destination.namespace // ""' "$app_file")

  # Gather helm sources from either .spec.sources[] or .spec.source
  local helm_sources_json
  helm_sources_json=$(yq e -o=j -I=0 '(.spec.sources // [ .spec.source ]) | map(select(has("chart")))' "$app_file")

  if [[ "$helm_sources_json" == "[]" ]]; then
    echo "[SKIP] $dir: no helm sources in app.yaml (helmfile not created)"
  else
    echo "[MIGRATE] $dir: generating helmfile.yaml"

    # Determine CreateNamespace=true
    if yq e '((.spec.syncPolicy.syncOptions // [])[] | select(. == "CreateNamespace=true"))' "$app_file" >/dev/null 2>&1; then
      create_ns_flag="true"
    else
      create_ns_flag="false"
    fi

    # Start writing helmfile.yaml
    local hf="$dir/helmfile.yaml"
    {
      echo "repositories:"
      echo "$helm_sources_json" | yq e -p=json -o=y '.[] | .repoURL' - | sort -u | while read -r url; do
        if [[ -n "$url" && "$url" != "null" ]]; then
          rname=$(slug_repo_name "$url")
          echo "  - name: $rname"
          echo "    url: $url"
        fi
      done
      echo
      echo "releases:"
    } > "$hf"

  # Iterate helm sources to create releases
    local count
    count=$(echo "$helm_sources_json" | yq e -p=json 'length' -)
    for ((i=0; i<count; i++)); do
      local repoURL chart version rname rchart
      repoURL=$(echo "$helm_sources_json" | yq e -p=json -o=y ".[$i].repoURL" -)
      chart=$(echo "$helm_sources_json" | yq e -p=json -o=y ".[$i].chart" -)
      version=$(echo "$helm_sources_json" | yq e -p=json -o=y ".[$i].targetRevision" -)
      rname=$(slug_repo_name "$repoURL")
      rchart="$rname/$chart"

      # Decide release name: use chart name
      local rel_name
      rel_name="$chart"

      {
        echo "  - name: $rel_name"
        if [[ -n "$ns" && "$ns" != "null" ]]; then
          echo "    namespace: $ns"
        fi
        echo "    chart: $rchart"
        if [[ -n "$version" && "$version" != "null" ]]; then
          echo "    version: $version"
        fi
        if [[ "$create_ns_flag" == "true" ]]; then
          echo "    createNamespace: true"
        fi
        echo "    values:"
        # Prefer a local values.yaml if present
        if [[ -f "$dir/values.yaml" ]]; then
          echo "      - values.yaml"
        fi
        # Inline valuesObject if present
        local vo_yaml
        vo_yaml=$(echo "$helm_sources_json" | yq e -p=json '.['"$i"'].helm.valuesObject // {}' -)
        if [[ "$vo_yaml" != "{}" ]]; then
        echo "      -"
        echo "$vo_yaml" | sed 's/^/        /'
        fi
      } >> "$hf"
    done
  fi

  # Update app.yaml to only include the folder Git source
  local rel_path
  rel_path="k8s/$(basename "$dir")"

  # Build a minimal sources array with folder-only Git
  # Write git source yaml to a temporary file
  tmp_git_src="$dir/.git-source.tmp.yaml"
  cat > "$tmp_git_src" <<YAML
- repoURL: '$REPO_GIT_URL'
  path: $rel_path
  directory:
    recurse: true
  targetRevision: HEAD
YAML

  # Always enforce Git-only sources to the folder
  if yq e 'has("spec")' "$app_file" >/dev/null; then
    tmpfile="$app_file.tmp"
    yq e 'del(.spec.source) | .spec.sources = load("'"$tmp_git_src"'")' "$app_file" > "$tmpfile"
    mv "$tmpfile" "$app_file"
  fi

  rm -f "$tmp_git_src"

}

main() {
  shopt -s nullglob
  local files=("$K8S_DIR"/*/app.yaml)
  for f in "${files[@]}"; do
    process_app "$f"
  done
}

main "$@"

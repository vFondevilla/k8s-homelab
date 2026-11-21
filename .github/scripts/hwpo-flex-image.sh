#!/usr/bin/env bash
# Helper for the "Build hwpo-flex image" workflow.
#
# All git and Docker output goes to a log file on the ephemeral runner. Only
# generic, actionable messages reach the public job log. The private source
# slug, the source token, and the private Dockerfile content never appear in
# the public job log.
#
# Runner prerequisites: bash, git, docker, curl, and python3. python3 is used
# by tag-check to validate registry response bodies. A missing prerequisite
# fails the run closed.
#
# Subcommands: validate, docker-init, fetch, build, login, tag-check, push,
# cleanup.
#
# docker-init creates a job-private Docker config directory (mode 0700) with a
# config.json (mode 0600) holding an empty auths entry for the target
# registry. The empty entry stops Docker from auto-detecting a native
# credential helper, so anonymous runs cannot read a previous machine login.
# The directory path is exported to later steps through GITHUB_ENV.
#
# tag-check queries the exact manifest that push would write and writes a
# missing output to GITHUB_OUTPUT: missing=false only when the registry
# answers HTTP 200 with a validated OCI or Docker image manifest or image
# index (media type, schemaVersion, manifest shape with required descriptor
# sizes and canonical digests, and a matching Docker-Content-Digest header
# when one is provided; conflicting repeated headers are rejected), and
# missing=true only
# when the request succeeds with HTTP 404 and a validated OCI error body
# (MANIFEST_UNKNOWN or NAME_UNKNOWN only). Any other outcome, including
# transport, encoding, configuration, proxy sign-in pages, or malformed or
# wrong-shape response bodies, exits non-zero and writes no output, so the
# push gate can never be satisfied by an unforeseen failure.
set -euo pipefail

COMMAND="${1:-}"

RUNNER_TEMP="${RUNNER_TEMP:-/tmp}"
LOG_FILE="${HWPO_FLEX_LOG_FILE:-${RUNNER_TEMP}/hwpo-flex-image.log}"
SOURCE_GIT_BASE_URL="${SOURCE_GIT_BASE_URL:-https://github.com}"
SRC_DIR="${SRC_DIR:-${RUNNER_TEMP}/hwpo-flex-src}"
SOURCE_GIT_DIR="${SOURCE_GIT_DIR:-${RUNNER_TEMP}/hwpo-flex-git}"
DOCKER_CONFIG_DIR="${RUNNER_TEMP}/hwpo-flex-docker-config"

log() {
  printf '%s\n' "$*" >&2
}

fail() {
  printf '::error::%s\n' "$*" >&2
  exit 1
}

require() {
  local name
  for name in "$@"; do
    if [ -z "${!name:-}" ]; then
      fail "Required configuration is missing: ${name}. Check the hwpo-flex-publish environment secrets and workflow variables."
    fi
  done
}

quiet() {
  "$@" >>"$LOG_FILE" 2>&1
}

# The image tag is always the full source SHA. The helper derives the expected
# image reference from configuration and refuses to query or push a reference
# that does not match, so an ambient override can never displace SOURCE_SHA.
expected_image_ref() {
  require REGISTRY REPOSITORY_PATH SOURCE_SHA
  printf '%s/%s:%s' "$REGISTRY" "$REPOSITORY_PATH" "$SOURCE_SHA"
}

assert_image_ref() {
  local expected
  expected="$(expected_image_ref)"
  if [ "${IMAGE_REF:-}" != "$expected" ]; then
    fail "The image reference does not match the registry, repository path, and source SHA configuration. Refusing to continue."
  fi
}

validate() {
  require SOURCE_REPOSITORY SOURCE_SHA
  if [[ ! "$SOURCE_REPOSITORY" =~ ^[^/[:space:]]+/[^/[:space:]]+$ ]]; then
    fail "The source repository slug is not set to owner/repo. Set the HWPO_FLEX_SOURCE_REPOSITORY environment secret."
  fi
  if [[ ! "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
    fail "The requested SHA is not a full lowercase 40-character hexadecimal commit SHA."
  fi
}

docker-init() {
  require REGISTRY GITHUB_ENV
  rm -rf "$DOCKER_CONFIG_DIR"
  mkdir -p "$DOCKER_CONFIG_DIR"
  chmod 700 "$DOCKER_CONFIG_DIR"
  # The empty auths entry for the target registry suppresses Docker's
  # automatic detection of native credential helpers.
  (
    umask 077
    printf '{"auths":{"%s":{}}}\n' "$REGISTRY" > "${DOCKER_CONFIG_DIR}/config.json"
  )
  chmod 600 "${DOCKER_CONFIG_DIR}/config.json"
  printf 'DOCKER_CONFIG=%s\n' "$DOCKER_CONFIG_DIR" >> "$GITHUB_ENV"
}

# The requested SHA must name a commit object itself. A tag object SHA would
# peel to a commit through rev-parse, so check the object type directly and
# reject anything that is not exactly a commit before any archive runs.
assert_commit_object() {
  local obj_type
  obj_type="$(git -C "$SOURCE_GIT_DIR" cat-file -t "$SOURCE_SHA" 2>>"$LOG_FILE")" || return 1
  [ "$obj_type" = "commit" ]
}

fetch() {
  require SOURCE_REPOSITORY SOURCE_SHA SOURCE_TOKEN SRC_DIR SOURCE_GIT_DIR
  rm -rf "$SOURCE_GIT_DIR" "$SRC_DIR"
  mkdir -p "$SOURCE_GIT_DIR" "$SRC_DIR"
  # Ephemeral, process-scoped HTTPS auth header. No token in any URL, no
  # global or on-disk git credentials. A base64 encoding failure aborts here,
  # before any git request.
  local git_auth_header
  git_auth_header="Authorization: Basic $(printf 'x-access-token:%s' "$SOURCE_TOKEN" | base64 | tr -d '\n')"
  export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.extraHeader GIT_CONFIG_VALUE_0="$git_auth_header"
  if quiet git init -q "$SOURCE_GIT_DIR" &&
    quiet git -C "$SOURCE_GIT_DIR" remote add origin "${SOURCE_GIT_BASE_URL}/${SOURCE_REPOSITORY}" &&
    quiet git -C "$SOURCE_GIT_DIR" fetch -q --depth 1 origin "$SOURCE_SHA" &&
    assert_commit_object &&
    { git -C "$SOURCE_GIT_DIR" archive "$SOURCE_SHA" | tar -C "$SRC_DIR" -x; } >>"$LOG_FILE" 2>&1; then
    unset GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0
  else
    unset GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0
    fail "Unable to fetch the application source at the requested SHA. Verify the SHA and the read-only source credentials, then retry."
  fi
  if [ -z "$(ls -A "$SRC_DIR")" ]; then
    fail "The fetched application source is empty. Verify the requested SHA."
  fi
}

build() {
  require SRC_DIR IMAGE_REF
  if ! quiet docker build --platform linux/amd64 -t "$IMAGE_REF" "$SRC_DIR"; then
    fail "The image build failed. Reproduce locally against the application repository at the requested SHA, or inspect the runner-local log at ${LOG_FILE}."
  fi
}

login() {
  require REGISTRY DOCKER_CONFIG
  if [ -n "${REGISTRY_USER:-}" ] && [ -n "${REGISTRY_PASSWORD:-}" ]; then
    # The password reaches Docker only through stdin, never through argv.
    if ! printf '%s' "$REGISTRY_PASSWORD" | quiet docker login "$REGISTRY" --username "$REGISTRY_USER" --password-stdin; then
      fail "Registry login failed. Check the registry credentials on the hwpo-flex-publish environment."
    fi
  elif [ -n "${REGISTRY_USER:-}" ] || [ -n "${REGISTRY_PASSWORD:-}" ]; then
    fail "Set both or neither of the HWPO_FLEX_REGISTRY_USERNAME and HWPO_FLEX_REGISTRY_PASSWORD environment secrets."
  else
    log "No registry credentials configured. Pushing anonymously."
  fi
}

# Shared strict-JSON registry document validator. All registry response
# bodies pass through one strict parser: duplicate object keys and non-JSON
# constants such as NaN and Infinity are rejected, so a crafted body cannot
# slip past a last-key-wins parser. Modes:
#   errors <body-file>
#     Exits 0 only when the body is a well-formed OCI errors document whose
#     entries are all recognized unknown-manifest codes. Rejects malformed,
#     empty, mixed, or denied documents.
#   manifest <body-file> <headers-file>
#     Exits 0 only when the final HTTP response headers (interim or proxy
#     CONNECT header blocks are ignored) carry an OCI or Docker image manifest
#     or image index media type and the body is a matching well-formed
#     manifest: schemaVersion 2, an optional mediaType field that agrees with
#     the header, and the correct descriptor shape (image manifests need a
#     config descriptor and a layers list; indexes need a non-empty manifests
#     list). Every descriptor must carry a non-negative integer size and a
#     canonical digest for a supported algorithm (sha224, sha256, sha384,
#     sha512, sha512-224, sha512-256); unknown algorithms fail closed.
#     Repeated Content-Type or Docker-Content-Digest headers must agree;
#     conflicting duplicates are rejected even when the last value is valid.
#     When a Docker-Content-Digest header is present it must match the body
#     bytes hashed with its own algorithm.
# Any unforeseen failure, including a missing python3, exits non-zero.
registry_json_check() {
  python3 - "$@" <<'PY'
import hashlib, json, re, sys

def reject_duplicate_keys(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate JSON object key")
    return dict(pairs)

def reject_non_json_constant(_):
    raise ValueError("non-JSON constant")

def strict_load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(
            fh,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_non_json_constant,
        )

def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)

# Registered digest algorithms with their hash constructor and canonical
# lowercase-hex length. Any other algorithm fails closed. The getattr guards
# keep the parser importable on Python builds without the SHA-512/224 and
# SHA-512/256 variants; those algorithms then fail closed there too.
DIGEST_ALGORITHMS = {}
for _name, _ctor_name, _length in (
    ("sha224", "sha224", 56),
    ("sha256", "sha256", 64),
    ("sha384", "sha384", 96),
    ("sha512", "sha512", 128),
    ("sha512-224", "sha512_224", 56),
    ("sha512-256", "sha512_256", 64),
):
    _ctor = getattr(hashlib, _ctor_name, None)
    if _ctor is not None:
        DIGEST_ALGORITHMS[_name] = (_ctor, _length)
CANONICAL_DIGEST_RE = re.compile(r"^[a-z0-9]+(?:[._+-][a-z0-9]+)*:[a-f0-9]+$")

def valid_digest(value):
    if not isinstance(value, str) or not CANONICAL_DIGEST_RE.fullmatch(value):
        return False
    algorithm, hex_part = value.split(":", 1)
    spec = DIGEST_ALGORITHMS.get(algorithm)
    if spec is None:
        return False
    return len(hex_part) == spec[1]

def is_descriptor(value):
    if not isinstance(value, dict):
        return False
    media_type = value.get("mediaType")
    if not isinstance(media_type, str) or not media_type:
        return False
    if not valid_digest(value.get("digest")):
        return False
    size = value.get("size")
    if not is_int(size) or size < 0:
        return False
    return True

def final_response_headers(path):
    # curl -D dumps every header block it saw, including interim 1xx and
    # proxy CONNECT responses. Only the last block that starts with an HTTP
    # status line is the final response.
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    final_block = None
    for block in re.split(r"\r?\n\r?\n", text):
        first_line = block.split("\n", 1)[0].strip()
        if first_line.upper().startswith("HTTP/"):
            final_block = block
    if final_block is None:
        return None
    headers = {}
    for line in final_block.splitlines():
        key, sep, rest = line.partition(":")
        if sep:
            headers.setdefault(key.strip().lower(), []).append(rest.strip())
    return headers

def single_header_value(headers, name):
    values = headers.get(name, [])
    if not values:
        return None
    if len(set(values)) > 1:
        raise ValueError("conflicting repeated %s header" % name)
    return values[0]

IMAGE_TYPES = {
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
}
INDEX_TYPES = {
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
}

def check_errors(body_path):
    data = strict_load(body_path)
    errors = data.get("errors") if isinstance(data, dict) else None
    if not isinstance(errors, list) or not errors:
        return False
    known = {"MANIFEST_UNKNOWN", "NAME_UNKNOWN"}
    for err in errors:
        if not isinstance(err, dict):
            return False
        code = err.get("code")
        if not isinstance(code, str) or code not in known:
            return False
    return True

def check_manifest(body_path, headers_path):
    headers = final_response_headers(headers_path)
    if headers is None:
        return False
    content_type = single_header_value(headers, "content-type")
    if content_type is None:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type not in IMAGE_TYPES | INDEX_TYPES:
        return False
    data = strict_load(body_path)
    if not isinstance(data, dict):
        return False
    if not is_int(data.get("schemaVersion")) or data["schemaVersion"] != 2:
        return False
    declared = data.get("mediaType")
    if declared is not None:
        if not isinstance(declared, str) or declared.strip().lower() != media_type:
            return False
    if media_type in IMAGE_TYPES:
        if not is_descriptor(data.get("config")):
            return False
        layers = data.get("layers")
        if not isinstance(layers, list) or not all(is_descriptor(d) for d in layers):
            return False
    else:
        manifests = data.get("manifests")
        if not isinstance(manifests, list) or not manifests:
            return False
        if not all(is_descriptor(d) for d in manifests):
            return False
    digest = single_header_value(headers, "docker-content-digest")
    if digest is not None:
        digest = digest.strip().lower()
        if not valid_digest(digest):
            return False
        algorithm = digest.split(":", 1)[0]
        constructor = DIGEST_ALGORITHMS[algorithm][0]
        with open(body_path, "rb") as fh:
            actual = algorithm + ":" + constructor(fh.read()).hexdigest()
        if actual != digest:
            return False
    return True

try:
    mode = sys.argv[1]
    if mode == "errors":
        ok = check_errors(sys.argv[2])
    elif mode == "manifest":
        ok = check_manifest(sys.argv[2], sys.argv[3])
    else:
        ok = False
except Exception:
    sys.exit(1)
sys.exit(0 if ok else 1)
PY
}

# Accepts a file containing a registry 404 response body. Exits 0 only when
# the body is a well-formed strict-JSON OCI errors document whose entries are
# all recognized unknown-manifest codes.
valid_unknown_manifest_body() {
  registry_json_check errors "$1"
}

# Accepts the response body file and curl header dump file of an HTTP 200
# manifest query. Exits 0 only when the response is a valid OCI or Docker
# image manifest or image index whose provided Docker-Content-Digest header
# (if any) matches the body bytes.
valid_manifest_response() {
  registry_json_check manifest "$1" "$2"
}

tag-check() {
  require REGISTRY REPOSITORY_PATH REGISTRY_BASE_URL SOURCE_SHA IMAGE_REF GITHUB_OUTPUT
  assert_image_ref
  if [[ ! "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
    fail "The image tag is not a full lowercase 40-character hexadecimal commit SHA. Refusing to query the registry."
  fi
  local accept="application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.docker.distribution.manifest.list.v2+json"
  local url="${REGISTRY_BASE_URL}/v2/${REPOSITORY_PATH}/manifests/${SOURCE_SHA}"
  local body="${RUNNER_TEMP}/hwpo-flex-tag-body.$$"
  local headers="${RUNNER_TEMP}/hwpo-flex-tag-headers.$$"
  local code
  if [ -n "${REGISTRY_USER:-}" ] && [ -n "${REGISTRY_PASSWORD:-}" ]; then
    local auth
    auth="Authorization: Basic $(printf '%s:%s' "$REGISTRY_USER" "$REGISTRY_PASSWORD" | base64 | tr -d '\n')"
    # The credential header goes through curl --config so it never appears in
    # the process argument list.
    code=$(curl -sS -o "$body" -D "$headers" -w '%{http_code}' --max-time 30 -H "Accept: ${accept}" --config - "$url" <<<"header = \"${auth}\"" 2>>"$LOG_FILE") || code=000
  else
    code=$(curl -sS -o "$body" -D "$headers" -w '%{http_code}' --max-time 30 -H "Accept: ${accept}" "$url" 2>>"$LOG_FILE") || code=000
  fi
  case "$code" in
    200)
      if valid_manifest_response "$body" "$headers"; then
        rm -f "$body" "$headers"
        log "Image tag already present in the registry."
        printf 'missing=false\n' >> "$GITHUB_OUTPUT"
        return 0
      fi
      rm -f "$body" "$headers"
      printf '::error::The registry answered HTTP 200 but did not return a valid image manifest for the tag. Refusing to report the tag as present or to push. Check registry connectivity and credentials.\n' >&2
      return 1
      ;;
    404)
      if valid_unknown_manifest_body "$body"; then
        rm -f "$body" "$headers"
        log "Image tag not present in the registry."
        printf 'missing=true\n' >> "$GITHUB_OUTPUT"
        return 0
      fi
      rm -f "$body" "$headers"
      printf '::error::The registry returned an unexpected 404 response that does not confirm a missing manifest. Refusing to push. Check registry connectivity and credentials.\n' >&2
      return 1
      ;;
    *)
      rm -f "$body" "$headers"
      printf '::error::Unable to confirm whether the image tag exists in the registry (HTTP %s). Refusing to push. Check registry connectivity and credentials.\n' "$code" >&2
      return 1
      ;;
  esac
}

push() {
  require IMAGE_REF
  assert_image_ref
  if ! quiet docker push "$IMAGE_REF"; then
    fail "The image push failed. Check registry connectivity and credentials, then retry. An existing tag is never overwritten."
  fi
}

cleanup() {
  local path
  for path in "${SRC_DIR:-}" "${SOURCE_GIT_DIR:-}" "${DOCKER_CONFIG:-}"; do
    case "$path" in
      "${RUNNER_TEMP}"/*) rm -rf "$path" ;;
    esac
  done
}

case "$COMMAND" in
  validate) validate ;;
  docker-init) docker-init ;;
  fetch) fetch ;;
  build) build ;;
  login) login ;;
  tag-check) tag-check ;;
  push) push ;;
  cleanup) cleanup ;;
  *) fail "Unknown command: ${COMMAND}. Expected one of: validate, docker-init, fetch, build, login, tag-check, push, cleanup." ;;
esac

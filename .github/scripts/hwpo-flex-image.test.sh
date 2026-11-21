#!/usr/bin/env bash
# Regression tests for hwpo-flex-image.sh. Exercises the real helper script.
# Uses only local fixtures: a file:// git repository, a fake docker shim, and
# a disposable loopback HTTP registry. Never touches GitHub or the real Zot.
# The fixture registry binds an ephemeral loopback port so concurrent test
# runs do not collide.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/hwpo-flex-image.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

SLUG="private-org/hwpo-flex-src-secret"
TOKEN="ghp_SENTINEL_TOKEN_0123456789abcdef"
DF_SENTINEL="SECRET_DOCKERFILE_LINE_SENTINEL"
USER_SENTINEL="reguser_SENTINEL"
PASS_SENTINEL="regpass_SENTINEL"

export RUNNER_TEMP="$WORK/runner-temp"
mkdir -p "$RUNNER_TEMP" "$WORK/bin"
export HWPO_FLEX_LOG_FILE="$RUNNER_TEMP/hwpo-flex-image.log"

PASS_COUNT=0
FAIL_COUNT=0
OUT=""
RC=0
GHOUT=""

report() {
  if [ "$1" -eq 0 ]; then
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "FAIL: $2"
    printf '%s\n' "$OUT" | sed 's/^/      | /'
  fi
}

run_script() {
  OUT="$("$@" 2>&1)"
  RC=$?
}

expect_ok() {
  [ "$RC" -eq 0 ]; report $? "exit 0 ($1)"
}

expect_fail() {
  [ "$RC" -ne 0 ]; report $? "non-zero exit ($1)"
}

expect_out_has() {
  printf '%s' "$OUT" | grep -qF -- "$1"; report $? "output contains: $1"
}

expect_out_hasnt() {
  if printf '%s' "$OUT" | grep -qF -- "$1"; then
    report 1 "output must not contain: $1"
  else
    report 0 "output must not contain: $1"
  fi
}

expect_ghout_is() {
  [ "$GHOUT" = "$1" ]; report $? "GITHUB_OUTPUT equals: $1 (got: ${GHOUT})"
}

expect_ghout_empty() {
  [ -z "$GHOUT" ]; report $? "GITHUB_OUTPUT empty (got: ${GHOUT})"
}

file_mode() {
  stat -f '%Lp' "$1" 2>/dev/null || stat -c '%a' "$1"
}

# Fake docker shim. Echoes a sentinel so redaction is observable. Captures
# login argv and stdin so credential delivery can be asserted.
cat > "$WORK/bin/docker" <<'EOF'
#!/usr/bin/env bash
echo "DOCKER_OUTPUT_SENTINEL line for $*"
case "$1" in
  build) [ "${FAKE_DOCKER_BUILD_FAIL:-0}" = "1" ] && exit 1 ;;
  push) [ "${FAKE_DOCKER_PUSH_FAIL:-0}" = "1" ] && exit 1 ;;
  login)
    [ -n "${FAKE_DOCKER_ARGS_FILE:-}" ] && printf '%s\n' "$*" >> "$FAKE_DOCKER_ARGS_FILE"
    [ -n "${FAKE_DOCKER_STDIN_FILE:-}" ] && cat > "$FAKE_DOCKER_STDIN_FILE"
    ;;
esac
exit 0
EOF
chmod +x "$WORK/bin/docker"

# base64 shim for pre-request failure injection. Passes through unless
# FAIL_BASE64=1, which simulates an encoding failure before any request.
cat > "$WORK/bin/base64" <<'EOF'
#!/usr/bin/env bash
if [ "${FAIL_BASE64:-0}" = "1" ]; then
  echo "base64: injected failure" >&2
  exit 1
fi
exec /usr/bin/base64 "$@"
EOF
chmod +x "$WORK/bin/base64"
export PATH="$WORK/bin:$PATH"

# Ephemeral loopback port so concurrent runs do not collide.
REG_PORT="$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"

# Fixture source repository served over file://.
mkdir -p "$WORK/gitroot/$(dirname "$SLUG")"
SRCREPO="$WORK/gitroot/$SLUG"
mkdir -p "$SRCREPO"
(
  cd "$SRCREPO"
  git init -q .
  git config user.email t@example.com
  git config user.name tester
  printf 'FROM scratch\n# %s\n' "$DF_SENTINEL" > Dockerfile
  git add Dockerfile
  git commit -qm init
)
GOOD_SHA="$(git -C "$SRCREPO" rev-parse HEAD)"
BAD_SHA="0000000000000000000000000000000000000000"

# 40-hex tags the fixture registry routes on.
S_PRESENT="$(printf 'a%.0s' {1..40})"
S_MISSING="$(printf 'b%.0s' {1..40})"
S_BOOM="$(printf 'c%.0s' {1..40})"
S_DENIED="$(printf 'd%.0s' {1..40})"
S_MALFORMED="$(printf 'e%.0s' {1..40})"
S_EMPTYERR="$(printf 'f%.0s' {1..40})"
S_MIXED="$(printf '9%.0s' {1..40})"
S_TEXT404="$(printf '8%.0s' {1..40})"
S_NAMEUNKNOWN="$(printf '7%.0s' {1..40})"
S_EMPTYBODY="$(printf '6%.0s' {1..40})"
S_DUPKEY_DENIED_FIRST="$(printf '5%.0s' {1..40})"
S_DUPKEY_UNKNOWN_FIRST="$(printf '4%.0s' {1..40})"
S_NAN="$(printf '3%.0s' {1..40})"
S_INFINITY="$(printf '2%.0s' {1..40})"
S_REGISTRY2="$(printf '1%.0s' {1..40})"
S_NONSTRING_CODE="$(printf '0%.0s' {1..40})"
# 200-path manifest fixtures.
S_HTML200="$(printf 'ab%.0s' {1..20})"
S_JSON200="$(printf 'ac%.0s' {1..20})"
S_WRONGCT200="$(printf 'ad%.0s' {1..20})"
S_OCI_MANIFEST="$(printf 'ae%.0s' {1..20})"
S_OCI_INDEX="$(printf 'af%.0s' {1..20})"
S_DOCKER_LIST="$(printf 'ba%.0s' {1..20})"
S_DIGEST_MISMATCH="$(printf 'd1%.0s' {1..20})"
S_NO_DIGEST="$(printf 'bc%.0s' {1..20})"
S_MANIFEST_DUPKEY="$(printf 'bd%.0s' {1..20})"
S_MANIFEST_BADSHAPE="$(printf 'be%.0s' {1..20})"
S_MANIFEST_SV1="$(printf 'bf%.0s' {1..20})"
S_EMPTY_LAYERS="$(printf 'ca%.0s' {1..20})"
S_EMPTY_INDEX="$(printf 'cb%.0s' {1..20})"
S_MANIFEST_MEDIAMISMATCH="$(printf 'd2%.0s' {1..20})"
S_NO_SIZE="$(printf 'd3%.0s' {1..20})"
S_NEG_SIZE="$(printf 'd4%.0s' {1..20})"
S_STR_SIZE="$(printf 'd5%.0s' {1..20})"
S_FLOAT_SIZE="$(printf 'e0%.0s' {1..20})"
S_BAD_DIGEST="$(printf 'd6%.0s' {1..20})"
S_SHORT_DIGEST="$(printf 'd7%.0s' {1..20})"
S_UNKNOWN_ALGO="$(printf 'd8%.0s' {1..20})"
S_SHA512_DESC="$(printf 'd9%.0s' {1..20})"
S_DUP_DIGEST_SAME="$(printf 'da%.0s' {1..20})"
S_DUP_DIGEST_CONFLICT="$(printf 'db%.0s' {1..20})"
S_DUP_CT_SAME="$(printf 'dc%.0s' {1..20})"
S_DUP_CT_CONFLICT="$(printf 'dd%.0s' {1..20})"
S_CONNECT_POLLUTE="$(printf 'de%.0s' {1..20})"
S_CONNECT_WRONG_FINAL="$(printf 'df%.0s' {1..20})"

base_env() {
  export SOURCE_REPOSITORY="$SLUG"
  export SOURCE_SHA="$GOOD_SHA"
  export SOURCE_TOKEN="$TOKEN"
  export SOURCE_GIT_BASE_URL="file://$WORK/gitroot"
  export SRC_DIR="$WORK/runner-temp/hwpo-flex-src"
  export SOURCE_GIT_DIR="$WORK/runner-temp/hwpo-flex-git"
  export IMAGE_REF="example.test/hwpo-flex:$GOOD_SHA"
  export REGISTRY="example.test"
  export REGISTRY_BASE_URL="http://127.0.0.1:$REG_PORT"
  export REPOSITORY_PATH="hwpo-flex"
  unset REGISTRY_USER REGISTRY_PASSWORD DOCKER_CONFIG
}

# --- validate ---------------------------------------------------------------
base_env
run_script "$SCRIPT" validate
expect_ok "validate good input"

run_script env SOURCE_SHA=deadbeef "$SCRIPT" validate
expect_fail "validate short sha"
expect_out_has "40-character"

run_script env SOURCE_REPOSITORY="not a slug" "$SCRIPT" validate
expect_fail "validate bad slug"
expect_out_hasnt "$SLUG"

run_script env SOURCE_REPOSITORY= "$SCRIPT" validate
expect_fail "validate missing slug"

# --- docker-init ------------------------------------------------------------
base_env
: > "$WORK/gh_env"
run_script env GITHUB_ENV="$WORK/gh_env" "$SCRIPT" docker-init
expect_ok "docker-init runs"
DC="$WORK/runner-temp/hwpo-flex-docker-config"
[ -d "$DC" ]; report $? "docker-init created config dir"
[ "$(file_mode "$DC")" = "700" ]; report $? "docker config dir mode is 0700"
[ "$(file_mode "$DC/config.json")" = "600" ]; report $? "config.json mode is 0600"
jq -e '.auths["example.test"] == {}' "$DC/config.json" > /dev/null 2>&1
report $? "config.json has empty auths entry for the target registry"
jq -e 'keys == ["auths"]' "$DC/config.json" > /dev/null 2>&1
report $? "config.json has no credential helper keys"
grep -qxF "DOCKER_CONFIG=$DC" "$WORK/gh_env"
report $? "docker-init exported DOCKER_CONFIG to GITHUB_ENV"

# --- fetch ------------------------------------------------------------------
base_env
run_script "$SCRIPT" fetch
expect_ok "fetch good sha"
expect_out_hasnt "$SLUG"
expect_out_hasnt "$TOKEN"
expect_out_hasnt "$DF_SENTINEL"
[ -f "$SRC_DIR/Dockerfile" ] && grep -q "$DF_SENTINEL" "$SRC_DIR/Dockerfile"
report $? "fetched tree contains Dockerfile"
[ ! -e "$SRC_DIR/.git" ]; report $? "build context has no .git"

base_env
run_script env SOURCE_SHA="$BAD_SHA" "$SCRIPT" fetch
expect_fail "fetch bad sha"
expect_out_hasnt "$SLUG"
expect_out_hasnt "$TOKEN"
expect_out_has "Unable to fetch the application source"

base_env
run_script env SOURCE_REPOSITORY="private-org/does-not-exist-secret" "$SCRIPT" fetch
expect_fail "fetch missing repo"
expect_out_hasnt "does-not-exist-secret"
expect_out_hasnt "$TOKEN"

base_env
run_script env SOURCE_TOKEN= "$SCRIPT" fetch
expect_fail "fetch missing token"

base_env
run_script env FAIL_BASE64=1 "$SCRIPT" fetch
expect_fail "fetch fails closed when base64 encoding fails"
expect_out_hasnt "$TOKEN"

# An annotated tag object SHA must be rejected: the fetched object is a tag,
# not a commit, so no source tree and no build may follow.
base_env
( cd "$SRCREPO" && git tag -a v-tagged -m 'annotated tag fixture' HEAD )
TAG_OBJ_SHA="$(git -C "$SRCREPO" for-each-ref --format='%(objectname)' refs/tags/v-tagged)"
[ "$(git -C "$SRCREPO" cat-file -t "$TAG_OBJ_SHA")" = "tag" ]; report $? "fixture tag object is a tag object"
run_script env SOURCE_SHA="$TAG_OBJ_SHA" "$SCRIPT" fetch
expect_fail "fetch rejects an annotated tag object SHA"
expect_out_has "Unable to fetch the application source"
[ -z "$(ls -A "$SRC_DIR" 2>/dev/null)" ]; report $? "fetch leaves no source tree for a tag object SHA"

# --- build ------------------------------------------------------------------
base_env
run_script "$SCRIPT" build
expect_ok "build success"
expect_out_hasnt "DOCKER_OUTPUT_SENTINEL"

run_script env FAKE_DOCKER_BUILD_FAIL=1 "$SCRIPT" build
expect_fail "build failure"
expect_out_hasnt "DOCKER_OUTPUT_SENTINEL"
expect_out_hasnt "$DF_SENTINEL"
expect_out_has "image build failed"

# --- login ------------------------------------------------------------------
base_env
mkdir -p "$WORK/runner-temp/hwpo-flex-docker-config"
: > "$WORK/docker_args"
run_script env DOCKER_CONFIG="$WORK/runner-temp/hwpo-flex-docker-config" \
  REGISTRY_USER="$USER_SENTINEL" REGISTRY_PASSWORD="$PASS_SENTINEL" \
  FAKE_DOCKER_ARGS_FILE="$WORK/docker_args" \
  FAKE_DOCKER_STDIN_FILE="$WORK/docker_stdin" \
  "$SCRIPT" login
expect_ok "login with paired credentials"
expect_out_hasnt "$USER_SENTINEL"
expect_out_hasnt "$PASS_SENTINEL"
grep -qF -- "--username $USER_SENTINEL" "$WORK/docker_args"
report $? "docker login received the configured username"
grep -qF -- "--password-stdin" "$WORK/docker_args"
report $? "docker login used --password-stdin, not an argv password"
grep -qxF -- "$PASS_SENTINEL" "$WORK/docker_stdin"
report $? "docker login received the password via stdin"
if printf '%s' "$(cat "$WORK/docker_args")" | grep -qF -- "$PASS_SENTINEL"; then
  report 1 "password must not appear in docker login argv"
else
  report 0 "password must not appear in docker login argv"
fi

base_env
run_script env DOCKER_CONFIG="$WORK/runner-temp/hwpo-flex-docker-config" \
  REGISTRY_USER="$USER_SENTINEL" "$SCRIPT" login
expect_fail "login with username only"
expect_out_hasnt "$USER_SENTINEL"
expect_out_has "both or neither"

run_script env DOCKER_CONFIG="$WORK/runner-temp/hwpo-flex-docker-config" \
  REGISTRY_PASSWORD="$PASS_SENTINEL" "$SCRIPT" login
expect_fail "login with password only"

base_env
run_script env REGISTRY_USER="$USER_SENTINEL" REGISTRY_PASSWORD="$PASS_SENTINEL" "$SCRIPT" login
expect_fail "login refuses without isolated DOCKER_CONFIG"

base_env
run_script env DOCKER_CONFIG="$WORK/runner-temp/hwpo-flex-docker-config" "$SCRIPT" login
expect_ok "login anonymous with isolated config"
expect_out_has "Pushing anonymously"

# --- fake registry ----------------------------------------------------------
cat > "$WORK/registry.py" <<'EOF'
import hashlib, http.server, json, sys

DOCKER_V2_CTYPE = "application/vnd.docker.distribution.manifest.v2+json"
OCI_MANIFEST_CTYPE = "application/vnd.oci.image.manifest.v1+json"
OCI_INDEX_CTYPE = "application/vnd.oci.image.index.v1+json"
DOCKER_LIST_CTYPE = "application/vnd.docker.distribution.manifest.list.v2+json"

def descriptor(media_type="application/vnd.oci.image.layer.v1.tar+gzip"):
    return {"mediaType": media_type, "digest": "sha256:" + "0" * 64, "size": 1234}

DOCKER_V2 = json.dumps({
    "schemaVersion": 2,
    "mediaType": DOCKER_V2_CTYPE,
    "config": descriptor("application/vnd.docker.container.image.v1+json"),
    "layers": [descriptor("application/vnd.docker.image.rootfs.diff.tar.gzip")],
})
OCI_MANIFEST = json.dumps({
    "schemaVersion": 2,
    "mediaType": OCI_MANIFEST_CTYPE,
    "config": descriptor("application/vnd.oci.image.config.v1+json"),
    "layers": [descriptor()],
})
OCI_INDEX = json.dumps({
    "schemaVersion": 2,
    "mediaType": OCI_INDEX_CTYPE,
    "manifests": [dict(descriptor(OCI_MANIFEST_CTYPE), platform={"os": "linux", "architecture": "amd64"})],
})
DOCKER_LIST = json.dumps({
    "schemaVersion": 2,
    "mediaType": DOCKER_LIST_CTYPE,
    "manifests": [dict(descriptor(DOCKER_V2_CTYPE), platform={"os": "linux", "architecture": "amd64"})],
})

def descriptor_without(**overrides):
    d = descriptor()
    for key, value in overrides.items():
        if value is None:
            del d[key]
        else:
            d[key] = value
    return d

def docker_v2_body(config=None, layers=None):
    return json.dumps({
        "schemaVersion": 2,
        "mediaType": DOCKER_V2_CTYPE,
        "config": config if config is not None
            else descriptor("application/vnd.docker.container.image.v1+json"),
        "layers": layers if layers is not None
            else [descriptor("application/vnd.docker.image.rootfs.diff.tar.gzip")],
    })

# An interim 1xx header block written before the real response. curl -D
# dumps interim blocks (and proxy CONNECT blocks the same way) ahead of the
# final response block. Their headers must be ignored by the parser. A real
# CONNECT block needs a live proxy; the interim block exercises the same
# multi-block dump path.
INTERIM_POLLUTE = (
    b"HTTP/1.1 100 Continue\r\n"
    b"X-Pollute: fixture-proxy\r\n"
    b"Content-Type: text/html\r\n"
    b"Docker-Content-Digest: sha256:" + b"f" * 64 + b"\r\n\r\n"
)

# Route values: (status, content-type, body, digest-mode[, preamble]).
# digest-mode: "auto" sends a correct Docker-Content-Digest, "wrong" a
# mismatched one, "none" omits it, "dup-correct"/"dup-conflict" send
# duplicate digests, "dup-ct-same"/"dup-ct-conflict" duplicate Content-Type.
# An optional fifth element is raw bytes written before the response.
ROUTES = {
    "a" * 40: (200, DOCKER_V2_CTYPE, DOCKER_V2, "auto"),
    "b" * 40: (404, "application/json", json.dumps(
        {"errors": [{"code": "MANIFEST_UNKNOWN", "message": "manifest unknown", "detail": {}}]}), "none"),
    "c" * 40: (500, "text/plain", "boom", "none"),
    "d" * 40: (401, "application/json", json.dumps(
        {"errors": [{"code": "DENIED", "message": "denied"}]}), "none"),
    "e" * 40: (404, "application/json", "{not json", "none"),
    "f" * 40: (404, "application/json", json.dumps({"errors": []}), "none"),
    "9" * 40: (404, "application/json", json.dumps(
        {"errors": [{"code": "MANIFEST_UNKNOWN", "message": "m"},
                    {"code": "DENIED", "message": "d"}]}), "none"),
    "8" * 40: (404, "text/html", "<html><body>404 Not Found</body></html>", "none"),
    "7" * 40: (404, "application/json", json.dumps(
        {"errors": [{"code": "NAME_UNKNOWN", "message": "repository name not known"}]}), "none"),
    "6" * 40: (404, "application/json", "", "none"),
    # Duplicate "code" keys. A last-key-wins parser would read the second
    # value, so each order must be rejected by duplicate-key detection.
    "5" * 40: (404, "application/json",
        '{"errors": [{"code": "DENIED", "code": "MANIFEST_UNKNOWN", "message": "m"}]}', "none"),
    "4" * 40: (404, "application/json",
        '{"errors": [{"code": "MANIFEST_UNKNOWN", "code": "DENIED", "message": "m"}]}', "none"),
    "3" * 40: (404, "application/json",
        '{"errors": [{"code": "MANIFEST_UNKNOWN", "message": NaN}]}', "none"),
    "2" * 40: (404, "application/json",
        '{"errors": [{"code": "MANIFEST_UNKNOWN", "message": Infinity}]}', "none"),
    # Canonical registry:2 manifest-unknown body.
    "1" * 40: (404, "application/json", json.dumps(
        {"errors": [{"code": "MANIFEST_UNKNOWN", "message": "manifest unknown"}]}), "none"),
    "0" * 40: (404, "application/json", json.dumps(
        {"errors": [{"code": 404, "message": "not a string code"}]}), "none"),
    # --- 200-path manifest fixtures ---------------------------------------
    # Captive-proxy sign-in page served under HTTP 200.
    "ab" * 20: (200, "text/html",
        "<html><body><h1>Sign in to continue</h1></body></html>", "none"),
    # Arbitrary JSON that is not a manifest, under a manifest-vetted status.
    "ac" * 20: (200, "application/json", json.dumps({"hello": "world"}), "none"),
    # Valid manifest JSON served under the wrong media type.
    "ad" * 20: (200, "application/json", DOCKER_V2, "auto"),
    "ae" * 20: (200, OCI_MANIFEST_CTYPE, OCI_MANIFEST, "auto"),
    "af" * 20: (200, OCI_INDEX_CTYPE, OCI_INDEX, "auto"),
    "ba" * 20: (200, DOCKER_LIST_CTYPE, DOCKER_LIST, "auto"),
    "d1" * 20: (200, DOCKER_V2_CTYPE, DOCKER_V2, "wrong"),
    "bc" * 20: (200, DOCKER_V2_CTYPE, DOCKER_V2, "none"),
    "bd" * 20: (200, DOCKER_V2_CTYPE,
        '{"schemaVersion": 2, "schemaVersion": 1, "mediaType": "%s",'
        ' "config": %s, "layers": []}' % (DOCKER_V2_CTYPE, json.dumps(descriptor())), "auto"),
    # Correct media type but no config descriptor.
    "be" * 20: (200, DOCKER_V2_CTYPE, json.dumps({
        "schemaVersion": 2, "mediaType": DOCKER_V2_CTYPE, "layers": []}), "auto"),
    "bf" * 20: (200, DOCKER_V2_CTYPE, json.dumps({
        "schemaVersion": 1, "mediaType": DOCKER_V2_CTYPE,
        "config": descriptor(), "layers": []}), "auto"),
    # A FROM-scratch image legitimately has zero layers.
    "ca" * 20: (200, DOCKER_V2_CTYPE, json.dumps({
        "schemaVersion": 2, "mediaType": DOCKER_V2_CTYPE,
        "config": descriptor("application/vnd.docker.container.image.v1+json"),
        "layers": []}), "auto"),
    "cb" * 20: (200, OCI_INDEX_CTYPE, json.dumps({
        "schemaVersion": 2, "mediaType": OCI_INDEX_CTYPE, "manifests": []}), "auto"),
    # Body mediaType field disagrees with the response header.
    "d2" * 20: (200, DOCKER_V2_CTYPE, json.dumps({
        "schemaVersion": 2, "mediaType": OCI_MANIFEST_CTYPE,
        "config": descriptor(), "layers": []}), "auto"),
    # --- descriptor field validation on the 200 path ------------------------
    # OCI descriptors require mediaType, digest, and a non-negative integer
    # size. Each defect below must fail closed.
    "d3" * 20: (200, DOCKER_V2_CTYPE, docker_v2_body(config=descriptor_without(size=None)), "auto"),
    "d4" * 20: (200, DOCKER_V2_CTYPE, docker_v2_body(config=descriptor_without(size=-1)), "auto"),
    "d5" * 20: (200, DOCKER_V2_CTYPE, docker_v2_body(config=descriptor_without(size="1234")), "auto"),
    "e0" * 20: (200, DOCKER_V2_CTYPE, docker_v2_body(config=descriptor_without(size=12.5)), "auto"),
    # Digest must be canonical: lowercase hex of the exact length for a
    # registered algorithm. Unknown algorithms fail closed.
    "d6" * 20: (200, DOCKER_V2_CTYPE, docker_v2_body(config=descriptor_without(digest="sha256:zz")), "auto"),
    "d7" * 20: (200, DOCKER_V2_CTYPE, docker_v2_body(config=descriptor_without(digest="sha256:" + "0" * 63)), "auto"),
    "d8" * 20: (200, DOCKER_V2_CTYPE, docker_v2_body(config=descriptor_without(digest="sha999:" + "0" * 64)), "auto"),
    # A valid sha512 descriptor digest is accepted.
    "d9" * 20: (200, DOCKER_V2_CTYPE, docker_v2_body(config=descriptor_without(digest="sha512:" + "a" * 128)), "auto"),
    # --- repeated header handling --------------------------------------------
    # Identical duplicate Docker-Content-Digest values are accepted.
    "da" * 20: (200, DOCKER_V2_CTYPE, DOCKER_V2, "dup-correct"),
    # Conflicting duplicates are rejected even though the last value matches.
    "db" * 20: (200, DOCKER_V2_CTYPE, DOCKER_V2, "dup-conflict"),
    # Identical duplicate Content-Type values are accepted.
    "dc" * 20: (200, DOCKER_V2_CTYPE, DOCKER_V2, "dup-ct-same"),
    # Conflicting duplicate Content-Type values are rejected.
    "dd" * 20: (200, DOCKER_V2_CTYPE, DOCKER_V2, "dup-ct-conflict"),
    # An interim header block before the real response must be ignored.
    "de" * 20: (200, DOCKER_V2_CTYPE, DOCKER_V2, "auto", INTERIM_POLLUTE),
    # The final response wins: a clean interim block cannot launder a wrong
    # final digest.
    "df" * 20: (200, DOCKER_V2_CTYPE, DOCKER_V2, "wrong", INTERIM_POLLUTE),
}

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        with open(sys.argv[2], "a") as f:
            f.write("PATH:%s\nAUTH:%s\nACCEPT:%s\n" % (
                self.path,
                self.headers.get("Authorization", "-"),
                self.headers.get("Accept", "-")))
        tag = self.path.rsplit("/", 1)[-1]
        route = ROUTES.get(tag, (404, "text/html", "<html>generic proxy 404</html>", "none"))
        code, ctype, body, digest_mode = route[:4]
        preamble = route[4] if len(route) > 4 else None
        payload = body.encode()
        if preamble:
            self.wfile.write(preamble)
        self.send_response(code)
        if digest_mode == "dup-ct-same":
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Type", ctype)
        elif digest_mode == "dup-ct-conflict":
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Type", "text/plain")
        else:
            self.send_header("Content-Type", ctype)
        correct = "sha256:" + hashlib.sha256(payload).hexdigest()
        if digest_mode == "auto":
            self.send_header("Docker-Content-Digest", correct)
        elif digest_mode == "wrong":
            self.send_header("Docker-Content-Digest", "sha256:" + "f" * 64)
        elif digest_mode == "dup-correct":
            self.send_header("Docker-Content-Digest", correct)
            self.send_header("Docker-Content-Digest", correct)
        elif digest_mode == "dup-conflict":
            # Conflicting duplicates: the last value matches, but the pair
            # must still be rejected.
            self.send_header("Docker-Content-Digest", "sha256:" + "f" * 64)
            self.send_header("Docker-Content-Digest", correct)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass

http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
EOF
: > "$WORK/registry.requests"
python3 "$WORK/registry.py" "$REG_PORT" "$WORK/registry.requests" &
REG_PID=$!
trap 'kill "$REG_PID" 2>/dev/null; rm -rf "$WORK"' EXIT
sleep 1

# tag-check writes its authorization to GITHUB_OUTPUT only. Every failure
# case must exit non-zero AND leave GITHUB_OUTPUT empty.
run_tag_check() {
  : > "$WORK/gh_output"
  OUT="$(env GITHUB_OUTPUT="$WORK/gh_output" "$@" 2>&1)"
  RC=$?
  GHOUT="$(cat "$WORK/gh_output" 2>/dev/null)"
}

base_env
run_tag_check env SOURCE_SHA="$S_PRESENT" IMAGE_REF="example.test/hwpo-flex:$S_PRESENT" "$SCRIPT" tag-check
expect_ok "tag-check present exits 0"
expect_ghout_is "missing=false"

base_env
run_tag_check env SOURCE_SHA="$S_MISSING" IMAGE_REF="example.test/hwpo-flex:$S_MISSING" "$SCRIPT" tag-check
expect_ok "tag-check missing exits 0"
expect_ghout_is "missing=true"

base_env
run_tag_check env SOURCE_SHA="$S_NAMEUNKNOWN" IMAGE_REF="example.test/hwpo-flex:$S_NAMEUNKNOWN" "$SCRIPT" tag-check
expect_ok "tag-check NAME_UNKNOWN exits 0"
expect_ghout_is "missing=true"

base_env
run_tag_check env SOURCE_SHA="$S_BOOM" IMAGE_REF="example.test/hwpo-flex:$S_BOOM" "$SCRIPT" tag-check
expect_fail "tag-check 5xx fails closed"
expect_ghout_empty
expect_out_has "Refusing to push"

base_env
run_tag_check env SOURCE_SHA="$S_DENIED" IMAGE_REF="example.test/hwpo-flex:$S_DENIED" "$SCRIPT" tag-check
expect_fail "tag-check 401 fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_MALFORMED" IMAGE_REF="example.test/hwpo-flex:$S_MALFORMED" "$SCRIPT" tag-check
expect_fail "tag-check malformed 404 body fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_EMPTYERR" IMAGE_REF="example.test/hwpo-flex:$S_EMPTYERR" "$SCRIPT" tag-check
expect_fail "tag-check empty errors array fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_EMPTYBODY" IMAGE_REF="example.test/hwpo-flex:$S_EMPTYBODY" "$SCRIPT" tag-check
expect_fail "tag-check empty 404 body fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_MIXED" IMAGE_REF="example.test/hwpo-flex:$S_MIXED" "$SCRIPT" tag-check
expect_fail "tag-check mixed unknown/denied errors fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_TEXT404" IMAGE_REF="example.test/hwpo-flex:$S_TEXT404" "$SCRIPT" tag-check
expect_fail "tag-check text/html 404 fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_DUPKEY_DENIED_FIRST" IMAGE_REF="example.test/hwpo-flex:$S_DUPKEY_DENIED_FIRST" "$SCRIPT" tag-check
expect_fail "tag-check duplicate code keys with DENIED first fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_DUPKEY_UNKNOWN_FIRST" IMAGE_REF="example.test/hwpo-flex:$S_DUPKEY_UNKNOWN_FIRST" "$SCRIPT" tag-check
expect_fail "tag-check duplicate code keys with MANIFEST_UNKNOWN first fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_NAN" IMAGE_REF="example.test/hwpo-flex:$S_NAN" "$SCRIPT" tag-check
expect_fail "tag-check NaN in 404 body fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_INFINITY" IMAGE_REF="example.test/hwpo-flex:$S_INFINITY" "$SCRIPT" tag-check
expect_fail "tag-check Infinity in 404 body fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_NONSTRING_CODE" IMAGE_REF="example.test/hwpo-flex:$S_NONSTRING_CODE" "$SCRIPT" tag-check
expect_fail "tag-check non-string error code fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_REGISTRY2" IMAGE_REF="example.test/hwpo-flex:$S_REGISTRY2" "$SCRIPT" tag-check
expect_ok "tag-check canonical registry:2 missing body exits 0"
expect_ghout_is "missing=true"

# --- 200-path manifest validation --------------------------------------------
# An HTTP 200 counts as "tag present" only when the response is a valid OCI
# or Docker image manifest or index. Every rejection below must exit non-zero
# and leave GITHUB_OUTPUT empty, so no push can proceed on a bogus 200.
base_env
run_tag_check env SOURCE_SHA="$S_HTML200" IMAGE_REF="example.test/hwpo-flex:$S_HTML200" "$SCRIPT" tag-check
expect_fail "tag-check HTML 200 proxy sign-in page fails closed"
expect_ghout_empty
expect_out_has "did not return a valid image manifest"

base_env
run_tag_check env SOURCE_SHA="$S_JSON200" IMAGE_REF="example.test/hwpo-flex:$S_JSON200" "$SCRIPT" tag-check
expect_fail "tag-check arbitrary JSON under 200 fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_WRONGCT200" IMAGE_REF="example.test/hwpo-flex:$S_WRONGCT200" "$SCRIPT" tag-check
expect_fail "tag-check manifest JSON under wrong media type fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_OCI_MANIFEST" IMAGE_REF="example.test/hwpo-flex:$S_OCI_MANIFEST" "$SCRIPT" tag-check
expect_ok "tag-check valid OCI image manifest exits 0"
expect_ghout_is "missing=false"

base_env
run_tag_check env SOURCE_SHA="$S_OCI_INDEX" IMAGE_REF="example.test/hwpo-flex:$S_OCI_INDEX" "$SCRIPT" tag-check
expect_ok "tag-check valid OCI image index exits 0"
expect_ghout_is "missing=false"

base_env
run_tag_check env SOURCE_SHA="$S_DOCKER_LIST" IMAGE_REF="example.test/hwpo-flex:$S_DOCKER_LIST" "$SCRIPT" tag-check
expect_ok "tag-check valid Docker manifest list exits 0"
expect_ghout_is "missing=false"

base_env
run_tag_check env SOURCE_SHA="$S_DIGEST_MISMATCH" IMAGE_REF="example.test/hwpo-flex:$S_DIGEST_MISMATCH" "$SCRIPT" tag-check
expect_fail "tag-check mismatched Docker-Content-Digest fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_NO_DIGEST" IMAGE_REF="example.test/hwpo-flex:$S_NO_DIGEST" "$SCRIPT" tag-check
expect_ok "tag-check valid manifest without digest header exits 0"
expect_ghout_is "missing=false"

base_env
run_tag_check env SOURCE_SHA="$S_MANIFEST_DUPKEY" IMAGE_REF="example.test/hwpo-flex:$S_MANIFEST_DUPKEY" "$SCRIPT" tag-check
expect_fail "tag-check manifest with duplicate JSON keys fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_MANIFEST_BADSHAPE" IMAGE_REF="example.test/hwpo-flex:$S_MANIFEST_BADSHAPE" "$SCRIPT" tag-check
expect_fail "tag-check manifest without config descriptor fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_MANIFEST_SV1" IMAGE_REF="example.test/hwpo-flex:$S_MANIFEST_SV1" "$SCRIPT" tag-check
expect_fail "tag-check schemaVersion 1 manifest fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_EMPTY_LAYERS" IMAGE_REF="example.test/hwpo-flex:$S_EMPTY_LAYERS" "$SCRIPT" tag-check
expect_ok "tag-check zero-layer scratch-style manifest exits 0"
expect_ghout_is "missing=false"

base_env
run_tag_check env SOURCE_SHA="$S_EMPTY_INDEX" IMAGE_REF="example.test/hwpo-flex:$S_EMPTY_INDEX" "$SCRIPT" tag-check
expect_fail "tag-check empty index manifests list fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_MANIFEST_MEDIAMISMATCH" IMAGE_REF="example.test/hwpo-flex:$S_MANIFEST_MEDIAMISMATCH" "$SCRIPT" tag-check
expect_fail "tag-check body mediaType disagreeing with header fails closed"
expect_ghout_empty

# --- descriptor field validation ----------------------------------------------
# OCI descriptors require a non-negative integer size and a canonical digest
# for a registered algorithm. A descriptor missing its size or carrying a
# bogus digest must never be accepted as proof that a tag exists.
base_env
run_tag_check env SOURCE_SHA="$S_NO_SIZE" IMAGE_REF="example.test/hwpo-flex:$S_NO_SIZE" "$SCRIPT" tag-check
expect_fail "tag-check descriptor without size fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_NEG_SIZE" IMAGE_REF="example.test/hwpo-flex:$S_NEG_SIZE" "$SCRIPT" tag-check
expect_fail "tag-check descriptor with negative size fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_STR_SIZE" IMAGE_REF="example.test/hwpo-flex:$S_STR_SIZE" "$SCRIPT" tag-check
expect_fail "tag-check descriptor with string size fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_FLOAT_SIZE" IMAGE_REF="example.test/hwpo-flex:$S_FLOAT_SIZE" "$SCRIPT" tag-check
expect_fail "tag-check descriptor with float size fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_BAD_DIGEST" IMAGE_REF="example.test/hwpo-flex:$S_BAD_DIGEST" "$SCRIPT" tag-check
expect_fail "tag-check descriptor with non-hex digest fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_SHORT_DIGEST" IMAGE_REF="example.test/hwpo-flex:$S_SHORT_DIGEST" "$SCRIPT" tag-check
expect_fail "tag-check descriptor with wrong-length sha256 digest fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_UNKNOWN_ALGO" IMAGE_REF="example.test/hwpo-flex:$S_UNKNOWN_ALGO" "$SCRIPT" tag-check
expect_fail "tag-check descriptor with unknown digest algorithm fails closed"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_SHA512_DESC" IMAGE_REF="example.test/hwpo-flex:$S_SHA512_DESC" "$SCRIPT" tag-check
expect_ok "tag-check descriptor with valid sha512 digest exits 0"
expect_ghout_is "missing=false"

# --- repeated header handling ---------------------------------------------------
# Identical duplicate headers are standard-conforming and accepted.
# Conflicting duplicates are rejected even when the last value is the valid
# one, so a last-header-wins parser cannot be spoofed.
base_env
run_tag_check env SOURCE_SHA="$S_DUP_DIGEST_SAME" IMAGE_REF="example.test/hwpo-flex:$S_DUP_DIGEST_SAME" "$SCRIPT" tag-check
expect_ok "tag-check identical duplicate Docker-Content-Digest exits 0"
expect_ghout_is "missing=false"

base_env
run_tag_check env SOURCE_SHA="$S_DUP_DIGEST_CONFLICT" IMAGE_REF="example.test/hwpo-flex:$S_DUP_DIGEST_CONFLICT" "$SCRIPT" tag-check
expect_fail "tag-check conflicting duplicate Docker-Content-Digest fails closed even when the last value matches"
expect_ghout_empty

base_env
run_tag_check env SOURCE_SHA="$S_DUP_CT_SAME" IMAGE_REF="example.test/hwpo-flex:$S_DUP_CT_SAME" "$SCRIPT" tag-check
expect_ok "tag-check identical duplicate Content-Type exits 0"
expect_ghout_is "missing=false"

base_env
run_tag_check env SOURCE_SHA="$S_DUP_CT_CONFLICT" IMAGE_REF="example.test/hwpo-flex:$S_DUP_CT_CONFLICT" "$SCRIPT" tag-check
expect_fail "tag-check conflicting duplicate Content-Type fails closed"
expect_ghout_empty

# --- interim/proxy header blocks --------------------------------------------------
# curl -D dumps interim 1xx and proxy CONNECT header blocks ahead of the
# final response. Their headers must not influence validation.
base_env
run_tag_check env SOURCE_SHA="$S_CONNECT_POLLUTE" IMAGE_REF="example.test/hwpo-flex:$S_CONNECT_POLLUTE" "$SCRIPT" tag-check
expect_ok "tag-check ignores interim header block before valid response exits 0"
expect_ghout_is "missing=false"

base_env
run_tag_check env SOURCE_SHA="$S_CONNECT_WRONG_FINAL" IMAGE_REF="example.test/hwpo-flex:$S_CONNECT_WRONG_FINAL" "$SCRIPT" tag-check
expect_fail "tag-check final response with wrong digest after interim block fails closed"
expect_ghout_empty

base_env
run_tag_check env REGISTRY_BASE_URL="http://127.0.0.1:1" SOURCE_SHA="$S_MISSING" IMAGE_REF="example.test/hwpo-flex:$S_MISSING" "$SCRIPT" tag-check
expect_fail "tag-check transport error fails closed"
expect_ghout_empty

base_env
run_tag_check env FAIL_BASE64=1 REGISTRY_USER="$USER_SENTINEL" REGISTRY_PASSWORD="$PASS_SENTINEL" \
  SOURCE_SHA="$S_MISSING" IMAGE_REF="example.test/hwpo-flex:$S_MISSING" "$SCRIPT" tag-check
expect_fail "tag-check pre-request base64 failure fails closed"
expect_ghout_empty
expect_out_hasnt "$PASS_SENTINEL"

base_env
OUT="$("$SCRIPT" tag-check 2>&1)"; RC=$?; GHOUT=""
[ "$RC" -ne 0 ]; report $? "tag-check without GITHUB_OUTPUT fails closed"

base_env
run_tag_check env SOURCE_SHA="$S_MISSING" IMAGE_REF="example.test/hwpo-flex:$S_PRESENT" "$SCRIPT" tag-check
expect_fail "tag-check refuses IMAGE_REF that does not match SOURCE_SHA"
expect_ghout_empty

base_env
run_tag_check env REGISTRY_USER="$USER_SENTINEL" REGISTRY_PASSWORD="$PASS_SENTINEL" \
  SOURCE_SHA="$S_PRESENT" IMAGE_REF="example.test/hwpo-flex:$S_PRESENT" "$SCRIPT" tag-check
expect_ok "tag-check authenticated exits 0"
expect_ghout_is "missing=false"
BASIC="$(printf '%s:%s' "$USER_SENTINEL" "$PASS_SENTINEL" | /usr/bin/base64 | tr -d '\n')"
grep -q "AUTH:Basic $BASIC" "$WORK/registry.requests"
report $? "registry request carried Basic auth"
grep -q "application/vnd.oci.image.index.v1+json" "$WORK/registry.requests"
report $? "registry request carried OCI manifest Accept header"
grep -qxF "PATH:/v2/hwpo-flex/manifests/$S_PRESENT" "$WORK/registry.requests"
report $? "tag-check queried the exact manifests path for the pushed tag"

# --- push -------------------------------------------------------------------
base_env
run_script "$SCRIPT" push
expect_ok "push success"
expect_out_hasnt "DOCKER_OUTPUT_SENTINEL"

run_script env FAKE_DOCKER_PUSH_FAIL=1 "$SCRIPT" push
expect_fail "push failure"
expect_out_hasnt "DOCKER_OUTPUT_SENTINEL"
expect_out_has "image push failed"

base_env
run_script env IMAGE_REF="example.test/hwpo-flex:$(printf 'z%.0s' {1..39})0" "$SCRIPT" push
expect_fail "push refuses IMAGE_REF that does not match SOURCE_SHA"

# --- cleanup ----------------------------------------------------------------
base_env
mkdir -p "$SRC_DIR" "$SOURCE_GIT_DIR" "$WORK/runner-temp/hwpo-flex-docker-config"
OUTSIDE="$WORK/outside-keep"
mkdir -p "$OUTSIDE"
run_script env DOCKER_CONFIG="$WORK/runner-temp/hwpo-flex-docker-config" "$SCRIPT" cleanup
expect_ok "cleanup runs"
[ ! -e "$SRC_DIR" ] && [ ! -e "$SOURCE_GIT_DIR" ] && [ ! -e "$WORK/runner-temp/hwpo-flex-docker-config" ]
report $? "cleanup removed src, git, and docker config dirs"
[ -d "$OUTSIDE" ]; report $? "cleanup left paths outside RUNNER_TEMP alone"

# --- misc -------------------------------------------------------------------
run_script "$SCRIPT" bogus-command
expect_fail "unknown command rejected"

# README dispatch example: single field in bash and zsh.
cat > "$WORK/bin/gh" <<'EOF'
#!/usr/bin/env bash
shift 2
for a in "$@"; do echo "ARG:$a"; done
EOF
chmod +x "$WORK/bin/gh"
sha="$GOOD_SHA"
BASH_OUT="$(bash -c "sha=$GOOD_SHA; gh api repos/x/dispatches -f event_type=build-hwpo-flex-image -f \"client_payload[sha]=\$sha\"")"
ZSH_OUT="$(zsh -c "sha=$GOOD_SHA; gh api repos/x/dispatches -f event_type=build-hwpo-flex-image -f \"client_payload[sha]=\$sha\"")"
printf '%s\n' "$BASH_OUT" | grep -qxF "ARG:client_payload[sha]=$GOOD_SHA"
report $? "bash sends client_payload[sha] as one field"
printf '%s\n' "$ZSH_OUT" | grep -qxF "ARG:client_payload[sha]=$GOOD_SHA"
report $? "zsh sends client_payload[sha] as one field"

echo "passed: $PASS_COUNT, failed: $FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]

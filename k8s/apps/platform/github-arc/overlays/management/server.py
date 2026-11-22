import base64
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OWNER = "vfondevilla"
OWNER_ID = 10423165
API = os.environ.get("GITHUB_API", "https://api.github.com")
# GitHub repository names allow dots and underscores. Slash and traversal-like input
# cannot pass this anchored single-component grammar.
SLUG = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def app_jwt(app_id, private_key_path, now=None):
    now = int(time.time() if now is None else now)
    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
    header = encode(b'{"alg":"RS256","typ":"JWT"}')
    claims = encode(json.dumps({"iat": now - 30, "exp": now + 480, "iss": str(app_id)}, separators=(",", ":")).encode())
    signing_input = (header + "." + claims).encode()
    signed = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", private_key_path],
        input=signing_input,
        check=True,
        capture_output=True,
    ).stdout
    return header + "." + claims + "." + encode(signed)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def request_json(url, token, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "arc-personal-repository-discovery",
    })
    with _OPENER.open(request, timeout=20) as response:
        return json.load(response), response.headers.get("Link", "")


def validate_installation(installation):
    if not isinstance(installation, dict):
        raise RuntimeError("personal App installation identity or repository selection is invalid")
    account = installation.get("account", {})
    if (type(account.get("id")) is not int or account["id"] != OWNER_ID
            or str(account.get("login", "")).casefold() != OWNER
            or account.get("type") != "User"
            or installation.get("repository_selection") != "all"):
        raise RuntimeError("personal App installation identity or repository selection is invalid")


def installation_token(app_id, install_id, key, call=request_json, jwt_factory=app_jwt):
    jwt = jwt_factory(app_id, key)
    installation, _ = call(f"{API}/app/installations/{install_id}", jwt)
    validate_installation(installation)
    data, _ = call(f"{API}/app/installations/{install_id}/access_tokens", jwt, "POST", {"permissions": {"metadata": "read"}})
    if "repository_selection" in data and data["repository_selection"] != "all":
        raise RuntimeError("personal App installation repository selection changed during token issuance")
    token = data.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("GitHub returned no installation token")
    return token


def next_page_url(link, expected_page):
    matches = re.findall(r'<([^>]+)>\s*;\s*rel="?next"?', link)
    if not matches:
        if re.search(r'rel="?next"?', link):
            raise RuntimeError("malformed GitHub pagination link")
        return None
    if len(matches) != 1:
        raise RuntimeError("ambiguous GitHub pagination link")
    parsed = urllib.parse.urlsplit(matches[0])
    query = urllib.parse.parse_qs(parsed.query)
    api = urllib.parse.urlsplit(API)
    if parsed.scheme != api.scheme or parsed.netloc != api.netloc or parsed.path != "/installation/repositories":
        raise RuntimeError("GitHub pagination escaped the installation endpoint")
    if query.get("page") != [str(expected_page)] or query.get("per_page") != ["100"]:
        raise RuntimeError("GitHub pagination skipped or repeated a page")
    return matches[0]


def _repository_listing(token, call):
    result = []
    inventory = []
    seen_ids = set()
    seen_names = set()
    page = 1
    expected_total = None
    while True:
        data, link = call(f"{API}/installation/repositories?page={page}&per_page=100", token)
        if not isinstance(data, dict) or type(data.get("total_count")) is not int or data["total_count"] < 0 or not isinstance(data.get("repositories"), list):
            raise RuntimeError("invalid installation repository response")
        if "repository_selection" in data and data["repository_selection"] != "all":
            raise RuntimeError("personal App installation repository selection changed during listing")
        if expected_total is None:
            expected_total = data["total_count"]
        elif expected_total != data["total_count"]:
            raise RuntimeError("installation repository count changed during pagination")
        repos = data["repositories"]
        if len(repos) > 100 or (page > 1 and not repos):
            raise RuntimeError("missing or oversized installation page")
        for repo in repos:
            if not isinstance(repo, dict):
                raise RuntimeError("malformed repository record")
            owner = repo.get("owner")
            if not isinstance(owner, dict) or str(owner.get("login", "")).casefold() != OWNER or owner.get("type") != "User":
                raise RuntimeError("installation returned a repository outside the configured user")
            name, rid = repo.get("name"), repo.get("id")
            if not isinstance(name, str) or not SLUG.fullmatch(name) or name in {".", ".."} or type(rid) is not int or rid <= 0 or repo.get("full_name") != f"{owner['login']}/{name}":
                raise RuntimeError("malformed repository identity")
            if type(repo.get("archived")) is not bool or type(repo.get("disabled")) is not bool:
                raise RuntimeError("malformed repository state")
            if rid in seen_ids or name.casefold() in seen_names:
                raise RuntimeError("duplicate repository in installation response")
            seen_ids.add(rid)
            seen_names.add(name.casefold())
            inventory.append((rid, name.casefold(), repo["archived"], repo["disabled"]))
            if not repo["archived"] and not repo["disabled"]:
                result.append({"repoName": f"{OWNER}/{name}", "repoID": str(rid), "repoURL": f"https://github.com/{OWNER}/{name}.git"})
        next_url = next_page_url(link, page + 1)
        if next_url:
            page += 1
            continue
        if len(seen_ids) != expected_total:
            raise RuntimeError("incomplete installation repository snapshot")
        return result, tuple(sorted(inventory)), page > 1


def repository_parameters(token, call=request_json):
    result, inventory, multipage = _repository_listing(token, call)
    if multipage:
        _second_result, second_inventory, _second_multipage = _repository_listing(token, call)
        if inventory != second_inventory:
            raise RuntimeError("installation repository inventory changed between complete listings")
    return result


def discover_parameters(app_id, install_id, key, call=request_json, jwt_factory=app_jwt):
    token = installation_token(app_id, install_id, key, call, jwt_factory)
    result = repository_parameters(token, call)
    # Recheck with a newly minted App JWT after the complete inventory is read.
    installation, _ = call(f"{API}/app/installations/{install_id}", jwt_factory(app_id, key))
    validate_installation(installation)
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_POST(self):
        token_path = os.environ.get("PLUGIN_TOKEN_FILE", "/var/run/plugin-token/plugin.arc-personal.token")
        try:
            with open(token_path, encoding="utf-8") as stream:
                expected = stream.read().strip()
        except OSError:
            expected = ""
        if not expected or self.headers.get("Authorization") != "Bearer " + expected:
            self.send_error(403)
            return
        if self.path != "/api/v1/getparams.execute":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1024 * 1024:
                raise ValueError("invalid request size")
            json.loads(self.rfile.read(length))
            credentials = os.environ.get("CREDENTIAL_DIR", "/var/run/github")
            with open(os.path.join(credentials, "app_id"), encoding="utf-8") as stream:
                app_id = stream.read().strip()
            with open(os.path.join(credentials, "installation_id"), encoding="utf-8") as stream:
                install_id = stream.read().strip()
            private_key_path = os.path.join(credentials, "private_key")
            params = discover_parameters(app_id, install_id, private_key_path)
            body = json.dumps({"output": {"parameters": params}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            self.send_error(502, "GitHub repository discovery failed")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "4355"))), Handler).serve_forever()

#!/usr/bin/env python3
"""Create ARC GitHub Apps through the manifest flow and store credentials in 1Password."""

import argparse
import base64
import html
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

MANIFESTS = Path(__file__).resolve().parents[1] / "k8s/apps/platform/github-arc/bootstrap"
TITLES = {"cloud-viking-io": "GitHub ARC cloud-viking-io", "vFondevilla": "GitHub ARC vFondevilla"}


def op(*args, payload=None):
    result = subprocess.run(
        ["op", *args, "--format=json"],
        input=json.dumps(payload) if payload is not None else None,
        text=True, capture_output=True,
    )
    if result.returncode:
        # Do not echo CLI output: it can contain submitted credentials.
        raise RuntimeError("1Password command failed. Check CLI authentication and vault access.")
    return json.loads(result.stdout)


def find_item(vault, title):
    matches = [item for item in op("item", "list", "--vault", vault) if item["title"] == title]
    if len(matches) > 1:
        raise RuntimeError(f"Multiple items named {title!r}. Resolve duplicates before continuing.")
    return op("item", "get", matches[0]["id"], "--vault", vault) if matches else None


def field(item, name):
    return next((f.get("value", "") for f in item.get("fields", []) if f.get("label") == name), "")


def save_item(vault, title, values, existing=None):
    item = existing or {"title": title, "category": "SECURE_NOTE", "fields": []}
    for name, value in values.items():
        matches = [f for f in item["fields"] if f.get("label") == name]
        if len(matches) > 1:
            raise RuntimeError(f"Duplicate field {name!r} in {title!r}.")
        if matches:
            matches[0]["value"] = str(value)
        else:
            item["fields"].append({"id": name, "label": name,
                                   "type": "CONCEALED" if name in ("private_key", "token") else "STRING",
                                   "value": str(value)})
    args = ("item", "edit", existing["id"]) if existing else ("item", "create")
    return op(*args, "--vault", vault, "-", payload=item)


def app_jwt(item):
    """Sign an App JWT with a PEM passed through a pipe to OpenSSL."""
    if not shutil.which("openssl"):
        raise RuntimeError("Install OpenSSL to discover the installation ID.")

    def encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=")

    now = int(time.time())
    message = encode(b'{"alg":"RS256","typ":"JWT"}') + b"." + encode(
        json.dumps({"iat": now - 60, "exp": now + 540, "iss": field(item, "app_id")}).encode())
    # A temporary anonymous file descriptor avoids key files and command-line secrets.
    read_fd, write_fd = os.pipe()
    process = None
    try:
        pem = field(item, "private_key").encode()
        if len(pem) > 8192:
            raise RuntimeError("Unexpected private key size.")
        # Start the reader before writing; this also handles small pipe buffers.
        process = subprocess.Popen(
            ["openssl", "dgst", "-sha256", "-sign", f"/dev/fd/{read_fd}"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(read_fd,))
        with os.fdopen(write_fd, "wb") as key_pipe:
            write_fd = None
            key_pipe.write(pem)
        try:
            signature, _ = process.communicate(message, timeout=30)
        except subprocess.TimeoutExpired:
            raise RuntimeError("OpenSSL signing timed out.") from None
        if process.returncode:
            raise RuntimeError("OpenSSL could not sign the App JWT.")
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()
    return (message + b"." + encode(signature)).decode()


def github(path, token, payload=None):
    request = urllib.request.Request("https://api.github.com" + path,
                                     data=json.dumps(payload).encode() if payload is not None else None,
                                     headers={"Authorization": "Bearer " + token,
                                              "Accept": "application/vnd.github+json",
                                              "User-Agent": "homelab-arc-bootstrap"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def installation_id(owner, item):
    installations = github("/app/installations?per_page=100", app_jwt(item))
    matches = [i for i in installations if i.get("account", {}).get("login", "").lower() == owner.lower()]
    if len(matches) != 1 or matches[0].get("suspended_at"):
        raise RuntimeError(f"No single active installation found for {owner}. Install the App first.")
    if owner == "vFondevilla" and matches[0].get("repository_selection") != "all":
        raise RuntimeError("Install the personal App with All repositories selected.")
    return int(matches[0]["id"])


def ensure_runner_group(item):
    """Create the configured organization group, with private repository access only."""
    owner = "cloud-viking-io"
    install_id = installation_id(owner, item)
    token = github(f"/app/installations/{install_id}/access_tokens", app_jwt(item),
                   {"permissions": {"organization_self_hosted_runners": "write"}})["token"]
    path = f"/orgs/{owner}/actions/runner-groups"
    page = 1
    while True:
        groups = github(f"{path}?per_page=100&page={page}", token)["runner_groups"]
        for group in groups:
            if group["name"] == owner:
                print("Existing organization runner group retained.")
                return group
        if len(groups) < 100:
            break
        page += 1
    group = github(path, token, {"name": owner, "visibility": "private", "allows_public_repositories": False})
    print("Organization runner group created with private repository access.")
    return group


def registration(owner, manifest, timeout, persist):
    """Accept one state-checked callback. Persist before returning an installation link."""
    state = secrets.token_urlsafe(32)
    launch = secrets.token_urlsafe(32)
    result = {}
    endpoint = (f"https://github.com/organizations/{owner}/settings/apps/new"
                if owner == "cloud-viking-io" else "https://github.com/settings/apps/new")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # The callback URL contains the temporary credential code.

        def reply(self, status, body):
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/" + launch:
                action = endpoint + "?state=" + state
                self.reply(200, '<h1>Create ARC GitHub App</h1><form method="post" action="' + action
                           + '"><input type="hidden" name="manifest" value="'
                           + html.escape(json.dumps(manifest), quote=True)
                           + '"><button>Create App on GitHub</button></form>')
                return
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path != "/callback" or not secrets.compare_digest(query.get("state", [""])[0], state):
                self.reply(400, "Invalid callback.")
                return
            code = query.get("code", [""])[0]
            if not code or len(code) > 256 or not code.isalnum():
                self.reply(400, "Missing or invalid registration code.")
                return
            try:
                request = urllib.request.Request(
                    "https://api.github.com/app-manifests/" + code + "/conversions",
                    data=b"", method="POST",
                    headers={"Accept": "application/vnd.github+json", "User-Agent": "homelab-arc-bootstrap"},
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    app = json.load(response)
                if app.get("owner", {}).get("login", "").lower() != owner.lower():
                    raise RuntimeError("The created App belongs to the wrong account.")
                if not app.get("id") or not app.get("pem") or not app.get("slug"):
                    raise RuntimeError("GitHub returned incomplete App credentials.")
                # Keep the response in memory if the vault write fails; never repeat conversion.
                result["app"] = app
                persist(app)
                result["saved"] = True
                link = "https://github.com/apps/" + urllib.parse.quote(app["slug"], safe="") + "/installations/new"
                self.reply(200, 'Credentials saved to 1Password. <a href="' + link + '">Install the App</a>. '
                           'Return to the terminal instructions after installation.')
            except (RuntimeError, OSError, ValueError):
                result["error"] = True
                self.reply(500, "Bootstrap failed. Read the terminal instructions; no credentials are displayed here.")

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        manifest["redirect_url"] = f"http://127.0.0.1:{server.server_port}/callback"
        url = f"http://127.0.0.1:{server.server_port}/{launch}"
        print(f"Open this local URL in your browser: {url}", flush=True)
        webbrowser.open(url)
        deadline = time.monotonic() + timeout
        server.timeout = 1
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if "app" in result and not result.get("saved"):
        print("GitHub created the App, but saving credentials failed. Keep this process open.", flush=True)
        while True:
            input("Restore 1Password access, then press Enter to retry saving: ")
            try:
                persist(result["app"])
                break
            except RuntimeError:
                print("1Password save failed; credentials remain in memory.", flush=True)
    elif not result.get("saved"):
        raise RuntimeError("Registration did not complete. Check GitHub App settings before retrying creation.")
    return result["app"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner", choices=[*TITLES, "plugin-token"])
    parser.add_argument("--vault", default="Lab", help="Vault accessible to the cluster's 1Password Connect (default: Lab)")
    parser.add_argument("--installation-id", type=int, help="Save an existing App installation ID; does not create an App")
    parser.add_argument("--discover-installation", action="store_true", help="Read the installation ID from GitHub and save it")
    parser.add_argument("--ensure-runner-group", action="store_true", help="Create the organization runner group if missing")
    parser.add_argument("--name", help="Override the globally unique GitHub App name")
    parser.add_argument("--timeout", type=int, default=900, help="Browser callback timeout in seconds")
    args = parser.parse_args()
    if args.installation_id is not None and (args.owner == "plugin-token" or args.installation_id <= 0):
        parser.error("--installation-id requires an App owner and a positive ID")
    if args.discover_installation and (args.owner == "plugin-token" or args.installation_id is not None):
        parser.error("--discover-installation requires an App owner and cannot accompany --installation-id")
    if args.ensure_runner_group and (args.owner != "cloud-viking-io" or args.discover_installation or args.installation_id is not None):
        parser.error("--ensure-runner-group requires cloud-viking-io and cannot accompany installation flags")
    if not 1 <= args.timeout <= 3500:
        parser.error("--timeout must be between 1 and 3500 seconds")
    if not shutil.which("op"):
        raise RuntimeError("Install the 1Password CLI and authenticate before continuing.")
    title = "ARC Argo plugin" if args.owner == "plugin-token" else TITLES[args.owner]
    existing = find_item(args.vault, title)
    if args.ensure_runner_group:
        if not existing or not field(existing, "app_id") or not field(existing, "private_key"):
            raise RuntimeError("App credentials are missing. Complete registration first.")
        ensure_runner_group(existing)
        return
    if args.owner == "plugin-token":
        if existing:
            if len(field(existing, "token").encode()) < 32:
                raise RuntimeError("Existing plugin token is missing or too short. Repair the item in 1Password.")
            print("Existing plugin token retained.")
        else:
            save_item(args.vault, title, {"token": secrets.token_urlsafe(32)})
            print("Plugin token created in 1Password.")
        return
    if args.installation_id is not None or args.discover_installation:
        if not existing or not field(existing, "app_id") or not field(existing, "private_key"):
            raise RuntimeError("App credentials are missing. Complete registration before saving the installation ID.")
        discovered = installation_id(args.owner, existing)
        if args.installation_id is not None and args.installation_id != discovered:
            raise RuntimeError(f"The supplied ID is not this App's installation ID. GitHub reports {discovered}.")
        args.installation_id = discovered
        current = field(existing, "installation_id")
        if current and current != str(args.installation_id):
            raise RuntimeError("A different installation ID already exists. Review the item in 1Password.")
        save_item(args.vault, title, {"installation_id": str(args.installation_id)}, existing)
        print("Installation ID saved. App credentials are ready for External Secrets.")
        return
    if existing:
        if not field(existing, "app_id") or not field(existing, "private_key"):
            raise RuntimeError("An incomplete item already exists. Repair it before creating another App.")
        print("Existing App credentials retained; no App created.")
        slug = field(existing, "slug")
    else:
        manifest = json.loads((MANIFESTS / f"{args.owner}.json").read_text())
        if args.name:
            manifest["name"] = args.name

        def persist(app):
            current = find_item(args.vault, title)
            if current and field(current, "app_id") != str(app["id"]):
                raise RuntimeError("A different App item appeared during registration. Resolve the conflict in 1Password.")
            save_item(args.vault, title, {"app_id": str(app["id"]), "private_key": app["pem"], "slug": app["slug"]}, current)

        app = registration(args.owner, manifest, args.timeout, persist)
        slug = app["slug"]
        print("App credentials saved to 1Password.")
    if slug:
        print(f"Install the App: https://github.com/apps/{urllib.parse.quote(slug, safe='')}/installations/new")
    print(f"Install on {args.owner}." + (" Select All repositories." if args.owner == "vFondevilla" else ""))
    print(f"Then run this script for {args.owner} with --discover-installation and the same --vault.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        # Unexpected subprocess/HTTP errors must not dump request bodies or credentials.
        print(f"Error: {error}" if isinstance(error, RuntimeError) else "Error: bootstrap operation failed.", file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("Bootstrap interrupted. Check GitHub and 1Password before retrying.", file=sys.stderr)
        sys.exit(1)

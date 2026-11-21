import base64
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "server.py"
SPEC = importlib.util.spec_from_file_location("arc_discovery", MODULE_PATH)
arc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arc)


def repo(name="project", rid=123, owner="vFondevilla", owner_type="User", **extra):
    return {"name": name, "id": rid, "full_name": f"{owner}/{name}", "owner": {"login": owner, "type": owner_type}, "archived": False, "disabled": False, **extra}


def page(records, total=None):
    return {"total_count": len(records) if total is None else total, "repositories": records}


class DiscoveryTests(unittest.TestCase):
    def test_valid_repository_names_and_numeric_ids(self):
        records = [repo("has.dot", 1), repo("under_score", 2), repo(".github", 3)]
        actual = arc.repository_parameters("t", lambda *a, **k: (page(records), ""))
        self.assertEqual([entry["repoName"] for entry in actual], ["vfondevilla/has.dot", "vfondevilla/under_score", "vfondevilla/.github"])

    def test_pagination_is_sequential_and_complete(self):
        calls = []
        records = [repo(f"repo-{i}", i + 1) for i in range(101)]
        def call(url, token):
            number = int(url.split("page=")[1].split("&")[0])
            calls.append(number)
            batch = records[(number - 1) * 100:number * 100]
            link = f'<https://api.github.com/installation/repositories?page={number + 1}&per_page=100>; rel="next"' if number == 1 else ""
            return page(batch, 101), link
        self.assertEqual(len(arc.repository_parameters("t", call)), 101)
        self.assertEqual(calls, [1, 2, 1, 2])

    def test_short_page_next_link_and_empty_installation(self):
        records = [repo("one", 1), repo("two", 2)]
        calls = []
        def call(url, token):
            number = int(url.split("page=")[1].split("&")[0])
            calls.append(number)
            link = '<https://api.github.com/installation/repositories?page=2&per_page=100>; rel="next"' if number == 1 else ""
            return page(records[number - 1:number], 2), link
        self.assertEqual(len(arc.repository_parameters("t", call)), 2)
        self.assertEqual(calls, [1, 2, 1, 2])
        self.assertEqual(arc.repository_parameters("t", lambda *a, **k: (page([]), "")), [])

    def test_incomplete_unstable_repeated_or_malformed_pages_fail(self):
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            arc.repository_parameters("t", lambda *a, **k: (page([repo()], 2), ""))
        def unstable(url, token):
            n = int(url.split("page=")[1].split("&")[0])
            link = '<https://api.github.com/installation/repositories?page=2&per_page=100>; rel="next"' if n == 1 else ""
            return page([repo("p1" if n == 1 else "p2", n)], 2 if n == 1 else 3), link
        with self.assertRaisesRegex(RuntimeError, "count changed"):
            arc.repository_parameters("t", unstable)
        for link in (
            '<https://attacker.example/installation/repositories?page=2&per_page=100>; rel="next"',
            '<https://api.github.com/installation/repositories?page=3&per_page=100>; rel="next"',
        ):
            with self.subTest(link=link), self.assertRaises(RuntimeError):
                arc.repository_parameters("t", lambda *a, **k: (page([repo()], 2), link))
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            arc.repository_parameters("t", lambda *a, **k: (page([repo("a", 1), repo("b", 1)]), ""))

    def test_same_cardinality_interleaved_multipage_inventory_fails(self):
        first = [repo(f"repo-{i}", i + 1) for i in range(101)]
        second = [dict(record) for record in first]
        second[-1] = repo("replacement", 999)
        pass_number = 0

        def call(url, _token):
            nonlocal pass_number
            page_number = int(url.split("page=")[1].split("&")[0])
            if page_number == 1:
                pass_number += 1
            records = first if pass_number == 1 else second
            batch = records[(page_number - 1) * 100:page_number * 100]
            link = '<https://api.github.com/installation/repositories?page=2&per_page=100>; rel="next"' if page_number == 1 else ""
            return page(batch, 101), link

        with self.assertRaisesRegex(RuntimeError, "inventory changed"):
            arc.repository_parameters("t", call)

    def test_bad_identity_name_and_state_fail_closed(self):
        for record in (repo("../x"), repo("slash/name"), repo("foreign", owner="other"), repo("organization", owner_type="Organization"), repo("broken", archived="false")):
            with self.subTest(record=record), self.assertRaises(RuntimeError):
                arc.repository_parameters("t", lambda *a, **k: (page([record]), ""))

    def test_archived_and_disabled_are_counted_then_filtered(self):
        records = [repo("old", 1, archived=True), repo("off", 2, disabled=True), repo("live", 3)]
        self.assertEqual([item["repoID"] for item in arc.repository_parameters("t", lambda *a, **k: (page(records), ""))], ["3"])

    def test_installation_identity_selection_and_permissions(self):
        seen = []
        def call(url, token, method="GET", payload=None):
            seen.append((url, method, payload))
            if url.endswith("/456"):
                return {"account": {"id": arc.OWNER_ID, "login": "vFondevilla", "type": "User"}, "repository_selection": "all"}, ""
            return {"token": "fixture-token"}, ""
        self.assertEqual(arc.installation_token("123", "456", "key", call, lambda *_: "jwt"), "fixture-token")
        self.assertEqual(seen[1][2], {"permissions": {"metadata": "read"}})
        for account, selection in (({"id": 9, "login": "vFondevilla", "type": "User"}, "all"), ({"id": arc.OWNER_ID, "login": "vFondevilla", "type": "Organization"}, "all"), ({"id": arc.OWNER_ID, "login": "vFondevilla", "type": "User"}, "selected")):
            def invalid(url, token, method="GET", payload=None):
                return {"account": account, "repository_selection": selection}, ""
            with self.subTest(account=account, selection=selection), self.assertRaises(RuntimeError):
                arc.installation_token("123", "456", "key", invalid, lambda *_: "jwt")

    def test_production_discovery_rechecks_selection_after_inventory(self):
        account = {"id": arc.OWNER_ID, "login": "vFondevilla", "type": "User"}

        def run(mode):
            state = {"install_checks": 0, "inventory_pages": 0, "jwt_values": []}

            def jwt_factory(*_args):
                value = f"jwt-{len(state['jwt_values']) + 1}"
                state["jwt_values"].append(value)
                return value

            def call(url, token, method="GET", payload=None):
                if url.endswith("/app/installations/456"):
                    state["install_checks"] += 1
                    selection = "selected" if mode == "changed_after_inventory" and state["install_checks"] == 2 else "all"
                    return {"account": account, "repository_selection": selection}, ""
                if url.endswith("/access_tokens"):
                    self.assertEqual(token, "jwt-1")
                    self.assertEqual(payload, {"permissions": {"metadata": "read"}})
                    token_data = {"token": "fixture-token"}
                    if mode == "selected_token":
                        token_data["repository_selection"] = "selected"
                    return token_data, ""
                if url.startswith(f"{arc.API}/installation/repositories?"):
                    state["inventory_pages"] += 1
                    page_number = int(url.split("page=")[1].split("&")[0])
                    if mode == "selected_page" and page_number == 2:
                        return {**page([repo("second", 2)], 101), "repository_selection": "selected"}, ""
                    if mode == "selected_empty":
                        return {**page([], 0), "repository_selection": "selected"}, ""
                    if mode == "changed_after_inventory":
                        return page([], 0), ""
                    records = [repo(f"repo-{i}", i + 1) for i in range(101)]
                    batch = records[(page_number - 1) * 100:page_number * 100]
                    link = f'<https://api.github.com/installation/repositories?page={page_number + 1}&per_page=100>; rel="next"' if page_number == 1 else ""
                    return page(batch, 101), link
                raise AssertionError(f"unexpected GitHub request: {url}")

            result = arc.discover_parameters("123", "456", "key", call, jwt_factory)
            return result, state

        result, state = run("stable_all")
        self.assertEqual(len(result), 101)
        self.assertEqual(state["install_checks"], 2)
        self.assertEqual(state["jwt_values"], ["jwt-1", "jwt-2"])
        for mode in ("changed_after_inventory", "selected_page", "selected_empty", "selected_token"):
            with self.subTest(mode=mode), self.assertRaisesRegex(RuntimeError, "selection"):
                run(mode)

    def test_production_discovery_requires_selection_on_both_installation_reads(self):
        account = {"id": arc.OWNER_ID, "login": "vFondevilla", "type": "User"}

        def run(failing_read=None, bad_selection=None):
            checks = 0

            def call(url, _token, method="GET", payload=None):
                nonlocal checks
                if url.endswith("/app/installations/456"):
                    checks += 1
                    if checks == failing_read:
                        body = {"account": account}
                        if bad_selection != "missing":
                            body["repository_selection"] = bad_selection
                        return body, ""
                    return {"account": account, "repository_selection": "all"}, ""
                if url.endswith("/access_tokens"):
                    return {"token": "fixture-token"}, ""
                if url.startswith(f"{arc.API}/installation/repositories?"):
                    return page([]), ""
                raise AssertionError(f"unexpected GitHub request: {url}")

            return arc.discover_parameters("123", "456", "key", call, lambda *_: "jwt")

        self.assertEqual(run(), [])
        for read in (1, 2):
            for selection in ("missing", None, "selected"):
                with self.subTest(read=read, selection=selection), self.assertRaisesRegex(RuntimeError, "selection"):
                    run(read, selection)

    def test_authentication_and_later_page_failures_never_return_partial_results(self):
        def denied(*_args, **_kwargs):
            raise RuntimeError("401 Unauthorized")
        with self.assertRaisesRegex(RuntimeError, "401"):
            arc.installation_token("123", "456", "key", denied, lambda *_: "jwt")

        def second_page_fails(url, _token):
            number = int(url.split("page=")[1].split("&")[0])
            if number == 1:
                records = [repo(f"fixture-{index}", index + 1) for index in range(100)]
                return page(records, 101), '<https://api.github.com/installation/repositories?page=2&per_page=100>; rel="next"'
            raise RuntimeError("second page unavailable")
        with self.assertRaisesRegex(RuntimeError, "second page unavailable"):
            arc.repository_parameters("fixture-token", second_page_fails)

    def test_http_transport_does_not_forward_credentials_on_redirect(self):
        observed = []
        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):
                observed.append(self.headers.get("Authorization"))
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/stolen")
                self.end_headers()
            def log_message(self, *_): pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(HTTPError):
                arc.request_json(f"http://127.0.0.1:{server.server_port}/", "secret", "POST", {})
            self.assertEqual(observed, ["Bearer secret"])
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    @unittest.skipUnless(shutil.which("openssl"), "openssl is required for fixture key generation")
    def test_production_entrypoint_authenticated_http_and_github_flow(self):
        state = {"requests": [], "install_checks": 0, "selection_change": False}
        class GitHubFixture(BaseHTTPRequestHandler):
            def do_GET(self):
                state["requests"].append(("GET", self.path, self.headers.get("Authorization")))
                if self.path.startswith("/app/installations/"):
                    state["install_checks"] += 1
                    selection = "selected" if state["selection_change"] and state["install_checks"] == 4 else "all"
                    self.reply({"account": {"id": arc.OWNER_ID, "login": "vFondevilla", "type": "User"}, "repository_selection": selection})
                elif self.path.startswith("/installation/repositories?"):
                    self.reply(page([repo("a.name", 98)], 1))
                else:
                    self.send_error(404)
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                state["requests"].append(("POST", self.path, payload))
                self.reply({"token": "fixture-installation-token"})
            def reply(self, value):
                data = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            def log_message(self, *_): pass
        github = ThreadingHTTPServer(("127.0.0.1", 0), GitHubFixture)
        threading.Thread(target=github.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as tmp:
            cred = Path(tmp) / "credentials"
            cred.mkdir()
            (cred / "app_id").write_text("123")
            (cred / "installation_id").write_text("456")
            (cred / "plugin-token").write_text("fixture-plugin-token")
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(cred / "private_key")], check=True, capture_output=True)
            port = socket.socket()
            port.bind(("127.0.0.1", 0))
            app_port = port.getsockname()[1]
            port.close()
            env = {**os.environ, "PLUGIN_TOKEN_FILE": str(cred / "plugin-token"), "CREDENTIAL_DIR": str(cred), "GITHUB_API": f"http://127.0.0.1:{github.server_port}", "PORT": str(app_port)}
            process = subprocess.Popen([shutil.which("python3"), "-I", str(MODULE_PATH)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                endpoint = f"http://127.0.0.1:{app_port}/api/v1/getparams.execute"
                for _ in range(100):
                    try:
                        request = Request(endpoint, data=b"{}", method="POST", headers={"Authorization": "Bearer wrong"})
                        urlopen(request, timeout=0.2)
                    except HTTPError as exc:
                        if exc.code == 403:
                            break
                    except Exception:
                        time.sleep(0.05)
                request = Request(endpoint, data=b"{}", method="POST", headers={"Authorization": "Bearer fixture-plugin-token"})
                with urlopen(request, timeout=5) as response:
                    result = json.load(response)
                self.assertEqual(result["output"]["parameters"][0]["repoName"], "vfondevilla/a.name")
                self.assertEqual(state["requests"][1][2], {"permissions": {"metadata": "read"}})
                state["selection_change"] = True
                with self.assertRaises(HTTPError) as failure:
                    urlopen(request, timeout=5)
                self.assertEqual(failure.exception.code, 502)
            finally:
                process.terminate()
                process.wait(timeout=5)
                github.shutdown()
                github.server_close()

    @unittest.skipUnless(shutil.which("openssl"), "openssl is required for the RSA signing check")
    def test_app_jwt_uses_valid_rsa_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            key, public = Path(tmp) / "app.pem", Path(tmp) / "app.pub"
            signing_input, signature = Path(tmp) / "input", Path(tmp) / "signature"
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)], check=True, capture_output=True)
            subprocess.run(["openssl", "pkey", "-in", str(key), "-pubout", "-out", str(public)], check=True, capture_output=True)
            encoded = arc.app_jwt("12345", str(key), now=1700000000)
            header, claims, signed = encoded.split(".")
            signing_input.write_bytes(f"{header}.{claims}".encode())
            signature.write_bytes(base64.urlsafe_b64decode(signed + "=" * ((4 - len(signed) % 4) % 4)))
            subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(public), "-signature", str(signature), str(signing_input)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()

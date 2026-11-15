"""Exercise guest Caddy routing with test-only upstreams, never real Hermes.

Run: python3 k8s/apps/workloads/hermes-agent/guest/test_routes.py
Requires caddy on PATH. No root, port 80, credentials, or cluster access needed.
"""
import http.client
import http.server
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
from typing import cast
import unittest


class FixtureServer(http.server.ThreadingHTTPServer):
    label: str


class Upstream(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Deliberately return request metadata from a fixture, not an agent result.
        data = json.dumps({"upstream": cast(FixtureServer, self.server).label, "path": self.path,
                           "authorization": self.headers.get("Authorization"),
                           "host": self.headers.get("Host"),
                           "proto": self.headers.get("X-Forwarded-Proto")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstreams = []
        text = Path(__file__).with_name("Caddyfile").read_text()
        for port, label in [(8642, "api"), (9119, "web"), (8765, "real-estate")]:
            server = FixtureServer(("127.0.0.1", 0), Upstream)
            server.label = label
            threading.Thread(target=server.serve_forever, daemon=True).start()
            cls.upstreams.append(server)
            text = text.replace(f"127.0.0.1:{port}", f"127.0.0.1:{server.server_port}")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        text = "{\n admin off\n auto_https off\n}\n" + text.replace(":80 {", f":{cls.port} {{\n bind 127.0.0.1", 1)
        cls.tmp = tempfile.TemporaryDirectory(prefix="hermes-caddy-test-")
        config = Path(cls.tmp.name) / "Caddyfile"
        config.write_text(text)
        cls.log = (Path(cls.tmp.name) / "caddy.log").open("w+")
        cls.proc = subprocess.Popen(["caddy", "run", "--config", str(config), "--adapter", "caddyfile"], stdout=cls.log, stderr=cls.log)
        for _ in range(100):
            if cls.proc.poll() is not None:
                cls.log.seek(0)
                raise RuntimeError(cls.log.read())
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=.1):
                    return
            except OSError:
                time.sleep(.05)
        raise RuntimeError("Test Caddy did not start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        for server in cls.upstreams:
            server.shutdown()
            server.server_close()
        cls.log.close()
        cls.tmp.cleanup()

    def request(self, path, host="hermes.apps.fondevilla.io", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path, headers={"Host": host, **(headers or {})})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_web_root(self):
        status, _, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["upstream"], "web")

    def test_dashboard_api_not_sent_to_openai(self):
        _, _, body = self.request("/api/status")
        self.assertEqual(json.loads(body)["upstream"], "web")

    def test_openai_prefix_and_bearer_are_preserved(self):
        status, _, body = self.request("/openai/v1/models?check=1", headers={"Authorization": "Bearer test-only-not-a-real-secret"})
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(data["upstream"], "api")
        self.assertEqual(data["path"], "/v1/models?check=1")
        self.assertEqual(data["authorization"], "Bearer test-only-not-a-real-secret")
        self.assertEqual(data["proto"], "https")
        self.assertEqual(data["host"], "hermes.apps.fondevilla.io")

    def test_api_redirect(self):
        status, headers, _ = self.request("/openai")
        self.assertEqual(status, 308)
        self.assertEqual(headers["Location"], "/openai/")

    def test_legacy_real_estate_path(self):
        status, _, body = self.request("/inmobiliaria/listings", host="hermes.fondevilla.io")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["upstream"], "real-estate")
        self.assertEqual(json.loads(body)["path"], "/listings")

    def test_legacy_landing_page(self):
        status, _, body = self.request("/", host="hermes.fondevilla.io")
        self.assertEqual(status, 200)
        self.assertIn(b"Monitor inmobiliario", body)

    def test_unknown_host_cannot_access_dashboard(self):
        status, _, _ = self.request("/api/config", host="untrusted.example")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)

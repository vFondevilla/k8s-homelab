import importlib.util
import json
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "bootstrap-github-arc.py"
spec = importlib.util.spec_from_file_location("bootstrap_arc", SCRIPT)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def test_runner_group_created_for_private_repositories(self):
        with patch.object(bootstrap, "installation_id", return_value=123), \
                patch.object(bootstrap, "app_jwt", return_value="jwt"), \
                patch.object(bootstrap, "github", side_effect=[
                    {"token": "installation-token"}, {"runner_groups": []}, {"id": 7},
                ]) as github:
            self.assertEqual(bootstrap.ensure_runner_group({}), {"id": 7})
            self.assertEqual(github.call_args.args, (
                "/orgs/cloud-viking-io/actions/runner-groups", "installation-token",
                {"name": "cloud-viking-io", "visibility": "private", "allows_public_repositories": False},
            ))

    def test_existing_runner_group_is_retained(self):
        group = {"id": 7, "name": "cloud-viking-io", "visibility": "selected"}
        with patch.object(bootstrap, "installation_id", return_value=123), \
                patch.object(bootstrap, "app_jwt", return_value="jwt"), \
                patch.object(bootstrap, "github", side_effect=[
                    {"token": "installation-token"}, {"runner_groups": [group]},
                ]) as github:
            self.assertEqual(bootstrap.ensure_runner_group({}), group)
            self.assertEqual(github.call_count, 2)

    def test_manifest_permissions(self):
        expected = {
            "cloud-viking-io": {"organization_self_hosted_runners": "write", "metadata": "read"},
            "vFondevilla": {"administration": "write", "metadata": "read"},
        }
        for owner, permissions in expected.items():
            manifest = json.loads((bootstrap.MANIFESTS / f"{owner}.json").read_text())
            self.assertEqual(manifest["default_permissions"], permissions)
            self.assertFalse(manifest["public"])
            self.assertFalse(manifest["hook_attributes"]["active"])
            self.assertEqual(manifest["default_events"], [])

    def test_duplicate_titles_fail(self):
        with patch.object(bootstrap, "op", return_value=[{"title": "App"}, {"title": "App"}]):
            with self.assertRaisesRegex(RuntimeError, "Multiple items"):
                bootstrap.find_item("Lab", "App")

    def test_secret_sent_on_stdin_and_cli_error_redacted(self):
        with patch.object(bootstrap.subprocess, "run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "PRIVATE KEY"
            with self.assertRaisesRegex(RuntimeError, "1Password command failed") as caught:
                bootstrap.op("item", "create", "-", payload={"secret": "PRIVATE KEY"})
            self.assertNotIn("PRIVATE KEY", str(caught.exception))
            self.assertNotIn("PRIVATE KEY", repr(run.call_args.args))
            self.assertIn("PRIVATE KEY", run.call_args.kwargs["input"])

    def test_existing_item_edit_preserves_other_fields(self):
        existing = {"id": "item", "fields": [{"label": "private_key", "value": "PEM"}]}
        with patch.object(bootstrap, "op") as op:
            bootstrap.save_item("Lab", "App", {"installation_id": "123"}, existing)
            self.assertEqual(op.call_args.args[:3], ("item", "edit", "item"))
            self.assertEqual(bootstrap.field(op.call_args.kwargs["payload"], "private_key"), "PEM")

    def test_existing_plugin_is_not_rotated(self):
        with patch.object(bootstrap, "find_item", return_value={"fields": [{"label": "token", "value": "x" * 43}]}), \
                patch.object(bootstrap, "save_item") as save, \
                patch.object(bootstrap.shutil, "which", return_value="op"), \
                patch("sys.argv", [str(SCRIPT), "plugin-token"]):
            bootstrap.main()
            save.assert_not_called()

    def test_conflicting_installation_id_is_not_overwritten(self):
        existing = {"fields": [{"label": key, "value": value} for key, value in
                               [("app_id", "1"), ("private_key", "PEM"), ("installation_id", "2")]]}
        with patch.object(bootstrap, "find_item", return_value=existing), \
                patch.object(bootstrap, "installation_id", return_value=3), \
                patch.object(bootstrap, "save_item") as save, \
                patch.object(bootstrap.shutil, "which", return_value="op"), \
                patch("sys.argv", [str(SCRIPT), "vFondevilla", "--installation-id", "3"]):
            with self.assertRaisesRegex(RuntimeError, "different installation"):
                bootstrap.main()
            save.assert_not_called()

    def test_supplied_app_id_is_not_saved_as_installation_id(self):
        existing = {"fields": [{"label": "app_id", "value": "10"}, {"label": "private_key", "value": "PEM"}]}
        with patch.object(bootstrap, "find_item", return_value=existing), \
                patch.object(bootstrap, "installation_id", return_value=999), \
                patch.object(bootstrap, "save_item") as save, \
                patch.object(bootstrap.shutil, "which", return_value="op"), \
                patch("sys.argv", [str(SCRIPT), "vFondevilla", "--installation-id", "10"]):
            with self.assertRaisesRegex(RuntimeError, "not this App's installation ID"):
                bootstrap.main()
            save.assert_not_called()

    def test_callback_rejects_bad_state_then_converts_and_persists(self):
        launched = threading.Event()
        urls = []
        manifest = {"name": "test"}
        saved = []
        result = []
        app = {"id": 1, "pem": "SECRET PEM", "slug": "test", "owner": {"login": "vFondevilla"}}
        real_urlopen = urllib.request.urlopen

        def open_url(request, **kwargs):
            if isinstance(request, urllib.request.Request):
                import io
                self.assertEqual(request.method, "POST")
                return io.BytesIO(json.dumps(app).encode())
            return real_urlopen(request, **kwargs)

        def browser(url):
            urls.append(url)
            launched.set()

        def register():
            result.append(bootstrap.registration("vFondevilla", manifest, 5, saved.append))

        with patch.object(bootstrap.webbrowser, "open", side_effect=browser), \
                patch.object(bootstrap.urllib.request, "urlopen", side_effect=open_url):
            thread = threading.Thread(target=register, daemon=True)
            thread.start()
            self.assertTrue(launched.wait(3))
            with real_urlopen(urls[0]) as response:
                page = response.read().decode()
            import re
            state = re.search(r"state=([A-Za-z0-9_-]+)", page).group(1)
            callback = manifest["redirect_url"]
            with self.assertRaises(urllib.error.HTTPError) as caught:
                real_urlopen(callback + "?state=wrong&code=abc")
            self.assertEqual(caught.exception.code, 400)
            self.assertFalse(saved)
            with real_urlopen(callback + "?" + urllib.parse.urlencode({"state": state, "code": "abc"})) as response:
                body = response.read().decode()
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertNotIn("SECRET PEM", body)
            self.assertEqual(saved, [app])
            self.assertEqual(result, [app])


if __name__ == "__main__":
    unittest.main()

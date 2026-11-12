"""Exercise stack tasks without provider credentials or infrastructure access."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


INFRA = Path(__file__).resolve().parents[1]
TASK = shutil.which("task")
STUB = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["TEST_LOG"], "a") as log:
    log.write(json.dumps({"command": name, "args": args, "cwd": os.getcwd()}) + "\n")

if name in ("mise", "op"):
    command = args[args.index("--") + 1:]
    os.execvp(command[0], command)
elif name == "tofu":
    if args[:2] == ["workspace", "show"]:
        print(os.environ.get("TF_WORKSPACE", "default"))
    elif args[:2] == ["state", "list"]:
        mode = os.environ.get("TEST_STATE", "present")
        if mode == "error":
            sys.exit("backend unavailable")
        if mode == "present":
            print("unifi_bgp.gateway")
    elif args[0] == "plan":
        Path(next(a.split("=", 1)[1] for a in args if a.startswith("-out="))).write_text("plan")
elif name == "aws":
    if args[1] == "head-object":
        mode = os.environ.get("TEST_HEAD", "present")
        if mode == "missing":
            sys.exit("An error occurred (404) when calling the HeadObject operation: Not Found")
        if mode == "denied":
            sys.exit("An error occurred (403) when calling the HeadObject operation: Forbidden")
    elif args[1] == "copy-object" and os.environ.get("TEST_COPY") == "error":
        sys.exit("copy failed")
'''


@unittest.skipUnless(TASK, "Task CLI is required")
class StackWorkflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.infra = self.root / "infra"
        for directory in ("taskfiles", "scripts"):
            shutil.copytree(INFRA / directory, self.infra / directory,
                            ignore=shutil.ignore_patterns("__pycache__"))
        (self.infra / ".env.op").write_text("# shared references\n")
        self.stack = self.infra / "stacks/unifi"
        self.stack.mkdir(parents=True)
        shutil.copy(INFRA / "stacks/unifi/Taskfile.yml", self.stack / "Taskfile.yml")
        (self.stack / ".env.op").write_text("# stack references\n")
        (self.stack / "unifi.tfplan").write_text("reviewed plan")
        self.metadata = self.stack / ".terraform/terraform.tfstate"
        self.metadata.parent.mkdir()
        self.backend = {
            "backend": {"type": "s3", "config": {
                "endpoints": {"s3": "https://example.r2.cloudflarestorage.com"},
                "bucket": "homelab-tfstate", "key": "unifi/terraform.tfstate",
            }},
        }
        self.save_backend()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("mise", "op", "tofu", "aws", "terramate"):
            executable = self.bin / name
            executable.write_text(STUB)
            executable.chmod(0o755)
        self.log = self.root / "commands.jsonl"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "TEST_LOG": str(self.log),
            "R2_ACCOUNT_ID": "example",
            "R2_BUCKET": "homelab-tfstate",
        }
        for key in ("TF_DATA_DIR", "TF_WORKSPACE", "PLAN_FILE", "REQUIRED_RESOURCE"):
            self.env.pop(key, None)

    def save_backend(self):
        self.metadata.write_text(json.dumps(self.backend))

    def run_task(self, name):
        return subprocess.run([TASK, "--dir", str(self.stack), name],
                              env=self.env, text=True, capture_output=True)

    def events(self, command):
        if not self.log.exists():
            return []
        return [event for line in self.log.read_text().splitlines()
                if (event := json.loads(line))["command"] == command]

    def use_proxmox_stack(self):
        self.stack = self.infra / "stacks/proxmox/example"
        self.stack.mkdir(parents=True)
        shutil.copy(INFRA / "templates/proxmox-vm/Taskfile.yml", self.stack / "Taskfile.yml")
        (self.stack / "plan.tfplan").write_text("reviewed plan")
        self.metadata = self.stack / ".terraform/terraform.tfstate"
        self.metadata.parent.mkdir()
        self.backend["backend"]["config"]["key"] = "proxmox/example/terraform.tfstate"
        self.save_backend()

    def test_unifi_plan_uses_both_env_files_and_preserves_import_guard(self):
        result = self.run_task("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        op = self.events("op")[0]
        self.assertIn(f"--env-file={self.infra}/.env.op", op["args"])
        self.assertIn("--env-file=.env.op", op["args"])
        tofu = self.events("tofu")
        self.assertIn(["state", "list", "unifi_bgp.gateway"], [e["args"] for e in tofu])
        self.assertIn("-out=unifi.tfplan", tofu[-1]["args"])
        self.assertTrue(all(Path(e["cwd"]).resolve() == self.stack.resolve() for e in tofu))

    def test_init_passes_r2_configuration_without_state_migration(self):
        result = self.run_task("init")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.events("tofu")[0]["args"]
        self.assertEqual(args[0], "init")
        self.assertIn('-backend-config=bucket=homelab-tfstate', args)
        self.assertIn('-backend-config=endpoints={s3="https://example.r2.cloudflarestorage.com"}', args)
        self.assertNotIn("-migrate-state", args)

    def test_apply_requires_a_saved_plan(self):
        (self.stack / "unifi.tfplan").unlink()
        result = self.run_task("apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.events("op"))
        self.assertFalse(self.events("aws"))
        self.assertFalse(self.events("tofu"))

    def test_missing_unifi_resource_stops_plan(self):
        self.env["TEST_STATE"] = "missing"
        result = self.run_task("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("task import first", result.stderr)
        self.assertFalse(any(e["args"][0] == "plan" for e in self.events("tofu")))

    def test_backend_error_is_not_reported_as_missing_import(self):
        self.env["TEST_STATE"] = "error"
        result = self.run_task("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("backend unavailable", result.stderr)
        self.assertNotIn("task import first", result.stderr)

    def test_failed_backup_stops_unifi_apply(self):
        self.env["TEST_COPY"] = "error"
        result = self.run_task("apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.events("tofu"))
        self.assertEqual(len(self.events("aws")), 1)

    def test_unifi_apply_keeps_backup_prefix_and_saves_twice(self):
        result = self.run_task("apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        copies = self.events("aws")
        self.assertEqual(len(copies), 2)
        destinations = [e["args"][e["args"].index("--key") + 1] for e in copies]
        self.assertTrue(all(key.startswith("backups/unifi/") for key in destinations))
        self.assertNotEqual(*destinations)
        self.assertEqual(self.events("tofu")[0]["args"][-1], "unifi.tfplan")

    def test_new_proxmox_stack_can_apply_without_existing_state(self):
        self.use_proxmox_stack()
        self.env["TEST_HEAD"] = "missing"
        result = self.run_task("apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e["args"][1] for e in self.events("aws")],
                         ["head-object", "copy-object"])
        self.assertEqual(self.events("tofu")[0]["args"][-1], "plan.tfplan")
        self.assertIn("homelab-tfstate/proxmox/example/terraform.tfstate",
                      self.events("aws")[-1]["args"])

    def test_denied_state_access_stops_new_stack_apply(self):
        self.use_proxmox_stack()
        self.env["TEST_HEAD"] = "denied"
        result = self.run_task("apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.events("tofu"))

    def test_workspace_override_stops_apply(self):
        self.env["TF_WORKSPACE"] = "other"
        result = self.run_task("apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("default OpenTofu workspace", result.stderr)
        self.assertFalse(self.events("aws"))
        self.assertFalse(self.events("tofu"))

    def test_wrong_bucket_stops_apply(self):
        self.backend["backend"]["config"]["bucket"] = "wrong-bucket"
        self.save_backend()
        result = self.run_task("apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.events("aws"))
        self.assertFalse(self.events("tofu"))


if __name__ == "__main__":
    unittest.main()

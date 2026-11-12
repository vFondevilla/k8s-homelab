"""Check adoption and plan safeguards without router or backend access."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


STACK = Path(__file__).resolve().parents[1] / "stacks/mikrotik"


def load(name):
    spec = importlib.util.spec_from_file_location(name, STACK / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adopt = load("adopt")
check = load("check_no_changes")


class PlanChecks(unittest.TestCase):
    def plan(self, action=None):
        return {"resource_changes": [{
            "address": "routeros_ip_dns.switch",
            "mode": "managed",
            "change": {"actions": action or ["no-op"]},
        }]}

    def test_complete_unchanged_plan(self):
        self.assertEqual(check.inspect_plan(self.plan(), {"routeros_ip_dns.switch"}), 1)

    def test_empty_or_partial_plans_fail(self):
        for plan in ({}, self.plan()):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                check.inspect_plan(plan, {"routeros_ip_dns.switch", "restapi_object.ovpn_server"})

    def test_every_mutation_fails(self):
        for action in (["create"], ["update"], ["delete"], ["delete", "create"], ["forget"]):
            with self.subTest(action=action), self.assertRaises(ValueError):
                check.inspect_plan(self.plan(action), {"routeros_ip_dns.switch"})

    def test_imports_and_incomplete_plans_fail(self):
        imported = self.plan()
        imported["resource_changes"][0]["change"]["importing"] = {"id": "ip.dns"}
        for plan in (imported, {**self.plan(), "deferred_changes": [{}]}, {**self.plan(), "errored": True}):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                check.inspect_plan(plan, {"routeros_ip_dns.switch"})


class AdoptionChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".local").mkdir()
        (self.root / "imports.json").write_text(json.dumps({"routeros_ip_service.ssh": "ssh"}))
        self.ovpn = {"name": "ovpn-server1", "disabled": "true"}
        (self.root / "openvpn.json").write_text(json.dumps(self.ovpn))
        self.existing = {
            "type": "routeros_system_identity", "name": "switch", "mode": "managed",
            "instances": [{"attributes": {"id": "system.identity", "name": "MikroTik"}}],
        }
        self.state = {"version": 4, "serial": 7, "lineage": "preserve-this-lineage", "resources": [self.existing]}
        self.commands = []
        self.pushed = None
        self.fail_backup = False
        self.live = {
            "/ip/dns": {"servers": "10.1.0.1", "allow-remote-requests": "false"},
            "/ip/service": [{".id": "*4", "name": "ssh", "port": "22", "disabled": "false"}],
            "/interface/ovpn-server/server/*1?.proplist=disabled,name": self.ovpn,
        }

        def schema(fields):
            return {"version": 0, "block": {"attributes": {k: {"type": v} for k, v in fields.items()}}}

        self.schemas = {"provider_schemas": {
            "registry.opentofu.org/terraform-routeros/routeros": {"resource_schemas": {
                "routeros_ip_dns": schema({"id": "string", "servers": ["list", "string"], "allow_remote_requests": "bool"}),
                "routeros_ip_service": schema({"id": "string", "name": "string", "numbers": "string", "port": "number", "disabled": "bool"}),
            }},
            "registry.opentofu.org/mastercard/restapi": {"resource_schemas": {
                "restapi_object": schema({**{k: "string" for k in ["id", "object_id", "path", "read_path", "data", "api_response"]}, "api_data": ["map", "string"]}),
            }},
        }}

    def command(self, *args):
        self.commands.append(args)
        if args[-2:] == ("state", "pull"):
            return json.dumps(self.state)
        if args[-3:] == ("providers", "schema", "-json"):
            return json.dumps(self.schemas)
        if args[:2] == ("python3", "../../scripts/backup_state.py"):
            if self.fail_backup:
                raise SystemExit("backup failed")
            return ""
        if "push" in args:
            self.pushed = json.loads(Path(args[-1]).read_text())
            return ""
        raise AssertionError(f"Unexpected command: {args}")

    def execute(self):
        with patch.object(adopt, "ROOT", self.root), patch.object(adopt, "run", self.command), patch.object(adopt, "read_api", side_effect=lambda path: copy.deepcopy(self.live[path])):
            adopt.adopt_provider_gaps()

    def test_adoption_preserves_existing_state_and_uses_live_values(self):
        self.execute()
        self.assertEqual(self.pushed["lineage"], self.state["lineage"])
        self.assertEqual(self.pushed["serial"], 8)
        self.assertEqual(self.pushed["resources"][0], self.existing)
        resources = {r["type"]: r["instances"][0]["attributes"] for r in self.pushed["resources"]}
        self.assertEqual(resources["routeros_ip_dns"]["servers"], ["10.1.0.1"])
        self.assertEqual(resources["routeros_ip_service"]["id"], "ssh")
        self.assertEqual(resources["routeros_ip_service"]["port"], 22)
        self.assertEqual(json.loads(resources["restapi_object"]["data"]), self.ovpn)
        self.assertFalse(any("apply" in command or "-force" in command for command in self.commands))
        push_index = next(i for i, command in enumerate(self.commands) if "push" in command)
        self.assertIn("backup_state.py", self.commands[push_index - 1][1])
        self.assertEqual(json.loads((self.root / ".local/before-gap-adoption.tfstate").read_text()), self.state)

    def test_live_openvpn_mismatch_stops_before_state_write(self):
        self.live["/interface/ovpn-server/server/*1?.proplist=disabled,name"] = {**self.ovpn, "disabled": "false"}
        with self.assertRaisesRegex(SystemExit, "OpenVPN differs"):
            self.execute()
        self.assertIsNone(self.pushed)

    def test_failed_backup_prevents_state_write(self):
        self.fail_backup = True
        with self.assertRaisesRegex(SystemExit, "backup failed"):
            self.execute()
        self.assertIsNone(self.pushed)

    def test_completed_adoption_is_idempotent(self):
        self.execute()
        self.state = copy.deepcopy(self.pushed)
        self.pushed = None
        self.commands.clear()
        self.execute()
        self.assertIsNone(self.pushed)
        self.assertEqual(self.commands, [tuple(adopt.TOFU + ["state", "pull"])])


if __name__ == "__main__":
    unittest.main()

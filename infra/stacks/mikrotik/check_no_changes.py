#!/usr/bin/env python3
"""Require a refreshed, complete OpenTofu plan with zero resource changes."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TOFU = ["mise", "exec", "--", "tofu"]


def inspect_plan(plan, expected):
    resources = {
        item["address"]: item for item in plan.get("resource_changes", [])
        if item.get("mode") == "managed"
    }
    missing = expected - resources.keys()
    if missing:
        raise ValueError("The plan omits adopted resources: " + ", ".join(sorted(missing)))
    changed = {
        address: item["change"]["actions"] for address, item in resources.items()
        if item["change"]["actions"] != ["no-op"] or item["change"].get("importing")
    }
    if changed or plan.get("deferred_changes") or plan.get("errored"):
        raise ValueError("The plan contains changes, pending imports, or incomplete resources.")
    return len(resources)


def main():
    os.chdir(ROOT)
    os.umask(0o077)
    local = ROOT / ".local"
    local.mkdir(exist_ok=True, mode=0o700)
    result_file = local / "no-changes.json"
    result_file.unlink(missing_ok=True)
    workspace = subprocess.check_output(TOFU + ["workspace", "show"], text=True).strip()
    if workspace != "default":
        raise SystemExit("The no-change check requires the default workspace.")
    result = subprocess.run(TOFU + [
        "plan", "-input=false", "-no-color", "-lock-timeout=60s",
        "-detailed-exitcode", "-out=mikrotik.tfplan",
    ], capture_output=True, text=True)
    (local / "plan.log").write_text(result.stdout + result.stderr)
    print(result.stdout, end="")
    sys.stderr.write(result.stderr)
    if result.returncode:
        if result.returncode == 2:
            print("The live plan contains changes. Validation failed.", file=sys.stderr)
        raise SystemExit(result.returncode)

    raw = subprocess.check_output(TOFU + ["show", "-json", "mikrotik.tfplan"], text=True)
    (local / "plan.json").write_text(raw)
    expected = set(json.loads((ROOT / "imports.json").read_text()))
    expected.update({"routeros_ip_dns.switch", "restapi_object.ovpn_server"})
    try:
        count = inspect_plan(json.loads(raw), expected)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    files = sorted(ROOT.glob("*.tf")) + [ROOT / "openvpn.json", ROOT / "imports.json", ROOT / ".terraform.lock.hcl"]
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    result_file.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": os.environ["ROS_HOSTURL"],
        "plan_exit_code": result.returncode,
        "managed_resources": count,
        "add": 0,
        "change": 0,
        "destroy": 0,
        "pending_imports": 0,
        "configuration_sha256": hashes,
    }, indent=2) + "\n")
    print(f"Verified {count} managed resources: 0 to add, 0 to change, 0 to destroy.")


if __name__ == "__main__":
    main()

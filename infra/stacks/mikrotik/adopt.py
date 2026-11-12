#!/usr/bin/env python3
"""Adopt the existing CRS305 configuration without writing to the switch."""

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
TOFU = ["mise", "exec", "--", "tofu"]
OVPN_PATH = "/interface/ovpn-server/server"


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    return result.stdout


def read_api(path):
    """Use GET only. Credentials remain in memory."""
    auth = base64.b64encode(
        f"{os.environ['ROS_USERNAME']}:{os.environ['ROS_PASSWORD']}".encode()
    ).decode()
    request = Request(
        os.environ["REST_API_URI"].rstrip("/") + path,
        headers={"Authorization": f"Basic {auth}"},
        method="GET",
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def resource_state(schema, provider, resource_type, name, values):
    return {
        "mode": "managed",
        "type": resource_type,
        "name": name,
        "provider": f'provider["{provider}"]',
        "instances": [{
            "schema_version": schema["version"],
            "attributes": {
                key: values.get(key) for key in schema["block"]["attributes"]
            },
            "sensitive_attributes": [],
        }],
    }


def native_values(schema, live, identity):
    values = {"id": identity}
    for key, field in schema["block"]["attributes"].items():
        source = key.replace("_", "-")
        if key.startswith("___") or source not in live:
            continue
        value = live[source]
        kind = field["type"]
        if kind == "bool":
            if value not in ("true", "false"):
                raise ValueError(f"Unexpected boolean for {source}")
            value = value == "true"
        elif kind == "number":
            value = int(value)
        elif isinstance(kind, list) and kind[0] in ("set", "list"):
            value = value.split(",") if value else []
        values[key] = value
    return values


def adopt_provider_gaps():
    # DNS has no importer. Service imports return numeric IDs, but reads need
    # service names. The REST importer cannot restore its read projection.
    # Seed these bindings from live GETs; never apply configuration to adopt them.
    # The following normal plan refreshes both resources through their providers.
    state = json.loads(run(*TOFU, "state", "pull"))
    existing = {(r["type"], r["name"]) for r in state["resources"]}
    wanted = {("routeros_ip_dns", "switch"), ("restapi_object", "ovpn_server")}
    imports = json.loads((ROOT / "imports.json").read_text())
    services = {
        address.split(".")[1]: identity for address, identity in imports.items()
        if address.startswith("routeros_ip_service.")
    }
    wanted.update(("routeros_ip_service", name) for name in services)
    ethernet_missing = any(
        resource["type"] == "routeros_interface_ethernet"
        and any(not instance["attributes"].get("factory_name") for instance in resource["instances"])
        for resource in state["resources"]
    )
    if wanted <= existing and not ethernet_missing:
        print("All resources and import metadata are already adopted.", flush=True)
        return

    original = json.dumps(state)
    metadata_count = 0
    if ethernet_missing:
        interfaces = {item[".id"]: item for item in read_api("/interface/ethernet")}
        for resource in state["resources"]:
            if resource["type"] != "routeros_interface_ethernet":
                continue
            for instance in resource["instances"]:
                values = instance["attributes"]
                if values.get("factory_name"):
                    continue
                factory_name = interfaces[values["id"]]["default-name"]
                if values.get("default_name") != factory_name:
                    raise SystemExit("The imported Ethernet identity differs from the live interface.")
                # This required provider-only field is omitted by its importer.
                # RouterOS calls the same immutable identity default-name.
                values["factory_name"] = factory_name
                metadata_count += 1

    providers = json.loads(run(*TOFU, "providers", "schema", "-json"))["provider_schemas"]
    routeros = next(k for k in providers if k.endswith("/terraform-routeros/routeros"))
    restapi = next(k for k in providers if k.endswith("/mastercard/restapi"))
    additions = []
    if ("routeros_ip_dns", "switch") not in existing:
        schema = providers[routeros]["resource_schemas"]["routeros_ip_dns"]
        additions.append(resource_state(
            schema, routeros, "routeros_ip_dns", "switch",
            native_values(schema, read_api("/ip/dns"), "ip.dns"),
        ))

    live_services = {item["name"]: item for item in read_api("/ip/service")}
    for name, service in services.items():
        if ("routeros_ip_service", name) in existing:
            continue
        live = live_services[service]
        schema = providers[routeros]["resource_schemas"]["routeros_ip_service"]
        values = native_values(schema, live, service)
        values["numbers"] = service
        additions.append(resource_state(schema, routeros, "routeros_ip_service", name, values))

    if ("restapi_object", "ovpn_server") not in existing:
        expected = json.loads((ROOT / "openvpn.json").read_text())
        projection = ",".join(sorted(expected))
        read_path = f"{OVPN_PATH}/{{id}}?.proplist={projection}"
        live = read_api(read_path.replace("{id}", quote("*1", safe="*")))
        if live != expected:
            raise SystemExit("OpenVPN differs from openvpn.json. Inspect the live configuration before adoption.")
        payload = json.dumps(live, sort_keys=True, separators=(",", ":"))
        schema = providers[restapi]["resource_schemas"]["restapi_object"]
        additions.append(resource_state(
            schema, restapi, "restapi_object", "ovpn_server", {
                "id": "*1",
                "object_id": "*1",
                "path": OVPN_PATH,
                "read_path": read_path,
                "data": payload,
                "api_response": payload,
                "api_data": live,
            },
        ))

    run("python3", "../../scripts/backup_state.py")
    (ROOT / ".local" / "before-gap-adoption.tfstate").write_text(original)
    state["resources"].extend(additions)
    state["serial"] += 1
    target = ROOT / ".local" / "gap-adoption.tfstate"
    target.write_text(json.dumps(state))
    # Never use -force. Preserve the lineage and let OpenTofu check the serial.
    run(*TOFU, "state", "push", "-lock-timeout=60s", str(target))
    print(f"Adopted {len(additions)} provider gaps and {metadata_count} Ethernet identities from live reads. No switch writes.", flush=True)


def main():
    os.chdir(ROOT)
    os.umask(0o077)
    (ROOT / ".local").mkdir(exist_ok=True, mode=0o700)
    if run(*TOFU, "workspace", "show").strip() != "default":
        raise SystemExit("Adoption requires the default workspace.")
    board = read_api("/system/routerboard")
    if board.get("serial-number") != "HGW0A9T5001":
        raise SystemExit("This endpoint is not the expected CRS305 switch.")

    result = subprocess.run(TOFU + ["state", "list"], capture_output=True, text=True)
    if result.returncode and "No state file was found" not in result.stderr:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    existing = set(result.stdout.splitlines())
    imports = json.loads((ROOT / "imports.json").read_text())
    if not existing <= set(imports) | {"routeros_ip_dns.switch", "restapi_object.ovpn_server"}:
        raise SystemExit("The state contains unexpected resources. Inspect it before adoption.")
    run("python3", "../../scripts/backup_state.py", "--allow-missing")
    for number, (address, identity) in enumerate(imports.items(), 1):
        if address in existing or address.startswith("routeros_ip_service."):
            continue
        print(f"[{number}/{len(imports)}] Import {address}", flush=True)
        output = run(*TOFU, "import", "-input=false", "-no-color", "-lock-timeout=60s", address, identity)
        with (ROOT / ".local" / "import.log").open("a") as log:
            log.write(output)
    adopt_provider_gaps()
    print(run("python3", "../../scripts/backup_state.py"), end="")
    print("Adoption is complete. Run task check:no-changes.")


if __name__ == "__main__":
    main()

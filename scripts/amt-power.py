#!/usr/bin/env python3
"""Control Intel AMT power over WS-Management with credentials from 1Password."""

import argparse
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


ITEM = "5snwhqewoyf2iapuwnebnmkj7y"
VAULT = "2w4dyciswfctvp42ue7hn5znam"
ACCOUNT = "my.1password.com"
CIM = "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
SOAP = "http://www.w3.org/2003/05/soap-envelope"
ADDRESS = "http://schemas.xmlsoap.org/ws/2004/08/addressing"
WSMAN = "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
ENUM = "http://schemas.xmlsoap.org/ws/2004/09/enumeration"
# AMT rejects WS-Management operation timeouts below 30 seconds.
# Keep this server-side value separate from curl's client-side request deadline.
OPERATION_TIMEOUT = 60
ACTIONS = {"on": 2, "off": 12, "force-off": 8}
STATES = {2: "on", 3: "sleep-light", 4: "sleep-deep", 7: "hibernate", 8: "off"}


class AMTError(Exception):
    pass


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def endpoint(host, http=False, port=None):
    """Accept only hostnames/IPs, so credentials cannot be sent to an injected URL."""
    host = host.strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        address = ipaddress.ip_address(host)
        host = f"[{address}]" if address.version == 6 else str(address)
    except ValueError:
        labels = host.rstrip(".").split(".")
        if len(host) > 253 or not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in labels
        ):
            raise AMTError(f"Invalid target {host!r}. Use a hostname or IP without a port or URL.")
    scheme = "http" if http else "https"
    return f"{scheme}://{host}:{port or (16992 if http else 16993)}/wsman"


def credentials(args):
    command = ["op", "item", "get", args.item, "--vault", args.vault, "--format", "json"]
    if not os.environ.get("OP_SERVICE_ACCOUNT_TOKEN"):
        command += ["--account", args.account]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise AMTError("1Password timed out. Unlock the app or sign in with op signin.") from None
    if result.returncode:
        raise AMTError("Cannot read the 1Password item. Check op authentication and item access.")
    try:
        fields = json.loads(result.stdout)["fields"]
        username = next(f["value"] for f in fields if f.get("id") == "username")
        password = next(f["value"] for f in fields if f.get("id") == "password")
    except (ValueError, KeyError, TypeError, StopIteration):
        raise AMTError("The 1Password item must contain username and password fields.") from None
    if not username or not password or ":" in username:
        raise AMTError("The AMT username/password is empty, or the username contains a colon.")
    return username, password


def config_quote(value):
    """Escape curl config values. The config is sent through stdin, never argv."""
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise AMTError("A credential contains an unsupported control character.")
    return '"' + (value.replace("\\", "\\\\").replace('"', '\\"')
                  .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")) + '"'


class Client:
    def __init__(self, url, auth, args):
        self.url, self.auth, self.args = url, auth, args

    def request(self, resource, action, body, selectors="", timeout=None):
        xml = (
            f'<s:Envelope xmlns:s="{SOAP}" xmlns:a="{ADDRESS}" xmlns:w="{WSMAN}" xmlns:n="{ENUM}">'
            f'<s:Header><a:To>{escape(self.url)}</a:To>'
            f'<a:ReplyTo><a:Address>{ADDRESS}/role/anonymous</a:Address></a:ReplyTo>'
            f'<a:Action s:mustUnderstand="true">{escape(action)}</a:Action>'
            f'<w:ResourceURI s:mustUnderstand="true">{CIM}{resource}</w:ResourceURI>'
            f'<a:MessageID>uuid:{uuid.uuid4()}</a:MessageID>'
            f'<w:OperationTimeout>PT{OPERATION_TIMEOUT}S</w:OperationTimeout>{selectors}</s:Header>'
            f'<s:Body>{body}</s:Body></s:Envelope>'
        )
        config = "\n".join([
            "url = " + config_quote(self.url),
            "user = " + config_quote(":".join(self.auth)),
            "data-binary = " + config_quote(xml),
        ]) + "\n"
        limit = timeout if timeout is not None else self.args.timeout
        command = [
            "curl", "--disable", "--silent", "--digest", "--noproxy", "*",
            "--connect-timeout", str(min(5, limit)), "--max-time", str(limit),
            "--header", "Content-Type: application/soap+xml; charset=utf-8",
            "--write-out", "\n%{http_code}", "--config", "-",
        ]
        if self.args.insecure:
            command.append("--insecure")
        if self.args.ca_cert:
            command += ["--cacert", self.args.ca_cert]
        try:
            response = subprocess.run(command, input=config, capture_output=True, text=True, timeout=limit + 2)
        except subprocess.TimeoutExpired:
            raise AMTError("Request timed out. Check status before repeating a power command.") from None
        if response.returncode:
            hint = "Check the address, port, and network."
            if response.returncode == 60:
                hint = "Certificate verification failed. Use --ca-cert or explicitly use --insecure."
            elif response.returncode == 28:
                hint = "Request timed out. Check status before repeating a power command."
            raise AMTError(f"curl failed (exit {response.returncode}). {hint}")
        payload, _, status = response.stdout.rpartition("\n")
        if status in ("401", "403"):
            raise AMTError(f"AMT rejected authentication or access (HTTP {status}).")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            raise AMTError(f"Invalid AMT XML response (HTTP {status}).") from None
        fault = root.find(f".//{{{SOAP}}}Fault")
        if fault is not None:
            # Report structured diagnostics, not the full response or fault Detail.
            details = [element.text for element in fault.findall(f".//{{{SOAP}}}Value")]
            details += [element.text for element in fault.findall(f"{{{SOAP}}}Reason/{{{SOAP}}}Text")]
            diagnostic = " | ".join(value for value in details if value)
            for secret in sorted(self.auth, key=len, reverse=True):
                diagnostic = diagnostic.replace(secret, "<redacted>")
            diagnostic = "".join(char if char.isprintable() else " " for char in diagnostic)[:500]
            suffix = f": {diagnostic}" if diagnostic else ""
            raise AMTError(f"AMT returned a SOAP fault (HTTP {status}){suffix}.")
        if status != "200":
            raise AMTError(f"AMT returned HTTP {status}.")
        return root

    def status(self, deadline=None):
        body = "<n:Enumerate/>"
        action = "Enumerate"
        for _ in range(16):
            remaining = self.args.timeout
            if deadline is not None:
                remaining = min(remaining, deadline - time.monotonic())
                if remaining <= 0:
                    raise AMTError("Timed out waiting for the requested power state.")
            root = self.request("CIM_AssociatedPowerManagementService", f"{ENUM}/{action}", body, timeout=remaining)
            state = root.find(f".//{{{CIM}CIM_AssociatedPowerManagementService}}PowerState")
            if state is not None and state.text:
                try:
                    return int(state.text)
                except ValueError:
                    raise AMTError("AMT returned an invalid power state.") from None
            context = root.find(f".//{{{ENUM}}}EnumerationContext")
            if root.find(f".//{{{ENUM}}}EndOfSequence") is not None or context is None or not context.text:
                break
            body = (f"<n:Pull><n:EnumerationContext>{escape(context.text)}</n:EnumerationContext>"
                    "<n:MaxElements>32</n:MaxElements></n:Pull>")
            action = "Pull"
        raise AMTError("AMT did not return a power state.")

    def change(self, action):
        resource = "CIM_PowerManagementService"
        body = (
            f'<p:RequestPowerStateChange_INPUT xmlns:p="{CIM}{resource}">'
            f'<p:PowerState>{ACTIONS[action]}</p:PowerState><p:ManagedElement>'
            f'<a:Address>{ADDRESS}</a:Address><a:ReferenceParameters>'
            f'<w:ResourceURI>{CIM}CIM_ComputerSystem</w:ResourceURI><w:SelectorSet>'
            '<w:Selector Name="CreationClassName">CIM_ComputerSystem</w:Selector>'
            '<w:Selector Name="Name">ManagedSystem</w:Selector></w:SelectorSet>'
            '</a:ReferenceParameters></p:ManagedElement></p:RequestPowerStateChange_INPUT>'
        )
        selectors = ('<w:SelectorSet><w:Selector Name="Name">Intel(r) AMT Power Management Service'
                     '</w:Selector></w:SelectorSet>')
        root = self.request(resource, f"{CIM}{resource}/RequestPowerStateChange", body, selectors)
        result = root.find(f".//{{{CIM}{resource}}}ReturnValue")
        if result is None or result.text not in ("0", "4096"):
            code = result.text if result is not None and (result.text or "").isdigit() else "missing"
            raise AMTError(f"AMT rejected {action} (ReturnValue={code}). No fallback power command was sent.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", *ACTIONS], help="off requests graceful shutdown; force-off cuts power without OS shutdown")
    parser.add_argument("hosts", nargs="+", help="AMT hostnames or IP addresses (not OS addresses unless shared)")
    parser.add_argument("--http", action="store_true", help="use unencrypted HTTP on port 16992 instead of HTTPS on 16993")
    parser.add_argument("--port", type=positive, help="override the AMT port")
    tls = parser.add_mutually_exclusive_group()
    tls.add_argument("--insecure", action="store_true", help="disable TLS certificate verification")
    tls.add_argument("--ca-cert", help="CA certificate file for AMT TLS")
    parser.add_argument("--timeout", type=positive, default=70, help="client timeout per request in seconds (default: 70)")
    parser.add_argument("--wait", type=positive, metavar="SECONDS", help="poll until the target reaches on/off, or fail on timeout")
    parser.add_argument("--dry-run", action="store_true", help="show targets and actions without accessing 1Password or AMT")
    parser.add_argument("--item", default=ITEM, help="1Password item ID or name")
    parser.add_argument("--vault", default=VAULT, help="1Password vault ID or name")
    parser.add_argument("--account", default=ACCOUNT, help="1Password account (ignored with OP_SERVICE_ACCOUNT_TOKEN)")
    args = parser.parse_args(argv)
    if args.port and args.port > 65535:
        parser.error("--port must be between 1 and 65535")
    if args.http and (args.insecure or args.ca_cert):
        parser.error("TLS options cannot be used with --http")
    if args.action == "status" and args.wait:
        parser.error("--wait requires a power action")
    try:
        # Validate all targets before retrieving secrets or sending any command.
        urls = list(dict.fromkeys(endpoint(host, args.http, args.port) for host in args.hosts))
        if args.dry_run:
            for url in urls:
                print(f"{url}: {args.action} (dry run)")
            return 0
        for executable in ("op", "curl"):
            if not shutil.which(executable):
                raise AMTError(f"Required command not found: {executable}")
        auth = credentials(args)
        failed = False
        for url in urls:
            client = Client(url, auth, args)
            try:
                if args.action == "status":
                    state = client.status()
                    print(f"{url}: {STATES.get(state, 'unknown')} (PowerState={state})")
                    continue
                client.change(args.action)
                print(f"{url}: {args.action} request accepted", flush=True)
                if args.wait:
                    deadline = time.monotonic() + args.wait
                    expected = 2 if args.action == "on" else 8
                    while client.status(deadline) != expected:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise AMTError("Timed out waiting for the requested power state.")
                        time.sleep(min(2, remaining))
                    print(f"{url}: {STATES[expected]} confirmed")
            except AMTError as error:
                failed = True
                print(f"{url}: ERROR: {error}", file=sys.stderr)
        return 1 if failed else 0
    except (AMTError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted. Check status before repeating a power command.", file=sys.stderr)
        sys.exit(130)

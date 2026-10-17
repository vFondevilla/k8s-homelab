# AMT power control

`amt-power.py` controls Intel AMT through WS-Management and HTTP Digest authentication.
It accepts one or more AMT hostnames or IP addresses on each invocation.
It retrieves the shared username and password from the `AMT Credentials` 1Password item at runtime.
Credentials stay in memory and are passed to curl through stdin.

## Requirements

- Python 3.9 or later, `curl`, and the 1Password CLI (`op`). No Python packages are required.
- An authenticated 1Password CLI session, desktop app integration, or an `OP_SERVICE_ACCOUNT_TOKEN` with access to the item.
- Network access to each AMT interface from another computer.
- AMT credentials with remote power management permission.

The script defaults to item `5snwhqewoyf2iapuwnebnmkj7y`, vault `2w4dyciswfctvp42ue7hn5znam`, and account `my.1password.com`.
Use `--item`, `--vault`, or `--account` to override these values.
All targets in one invocation use the same credentials.

## Commands

Replace these example names with the current AMT hostnames or IP addresses.
Use AMT addresses, which can differ from the operating system addresses.

```sh
# Read the current power state.
python3 scripts/amt-power.py status amt-node01 amt-node02

# Power on selected computers and wait up to 60 seconds per computer.
python3 scripts/amt-power.py on amt-node01 amt-node02 --wait 60

# Request an orderly operating system shutdown.
python3 scripts/amt-power.py off amt-node01 amt-node02 --wait 90

# Preview an operation without accessing AMT or 1Password.
python3 scripts/amt-power.py off amt-node01 amt-node02 --dry-run
```

`off` requests AMT power state 12 (graceful shutdown).
It requires compatible firmware and operating system support.
The script never falls back to forced power-off.

**CAUTION:** `force-off` requests AMT power state 8 without an orderly operating system shutdown. Unsaved data can be lost.

```sh
python3 scripts/amt-power.py force-off amt-node01
```

The script does not drain Kubernetes nodes or stop workloads before shutdown.
If a node requires workload preparation, complete that preparation before a power command.

## Connection options

HTTPS on port 16993 is the default. TLS certificates are verified.
The default client timeout is 70 seconds per request.
The SOAP operation timeout is 60 seconds because AMT requires at least 30 seconds.
`--timeout` changes the client deadline only.

```sh
# Trust your AMT certificate authority.
python3 scripts/amt-power.py status amt-node01 --ca-cert /path/to/amt-ca.pem

# Explicitly disable certificate verification for a self-signed endpoint.
python3 scripts/amt-power.py status amt-node01 --insecure

# Use unencrypted HTTP for machines configured on port 16992.
python3 scripts/amt-power.py status 10.1.0.10 10.1.0.11 --http

# Override the port or request timeout.
python3 scripts/amt-power.py status amt-node01 --port 16993 --timeout 30
```

HTTP Digest authentication does not encrypt HTTP traffic.
The script does not automatically downgrade HTTPS or bypass certificate verification.
It bypasses HTTP proxies and ignores `.curlrc` to keep requests direct and predictable.

## Results

Without `--wait`, a successful power command reports that AMT accepted the request.
This response does not prove that the computer reached the requested state.
With `--wait`, the script polls AMT until the power state matches or the timeout expires.
An `on` state does not prove that the operating system or Kubernetes node is ready.

Targets are processed sequentially. Duplicate endpoints are processed once.
An error for one target does not prevent attempts for the remaining targets.
Exit status is `0` for success, `1` for an operation error, `2` for invalid CLI arguments, and `130` for interruption.

If a power request times out, read `status` before repeating the command.
The original request can still take effect after the connection closes.
AMT can reject power commands during an active KVM, SOL, or storage redirection session.

## Tests and protocol reference

Run the tests from the repository root:

```sh
python3 -B -m unittest discover -s scripts -p 'test_amt_power.py' -v
```

The tests use a local HTTP Digest server. They do not access real computers or 1Password.

Power state values follow Intel's [Change System Power State reference](https://software.intel.com/sites/manageability/AMT_Implementation_and_Reference_Guide/WordDocuments/changesystempowerstate.htm).
The operation timeout follows Intel's [WS-Management requirements](https://software.intel.com/sites/manageability/AMT_Implementation_and_Reference_Guide/WordDocuments/dsp0226webservicesformanagementwsmanagementspecification.htm).

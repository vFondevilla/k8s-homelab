# MikroTik SFP switch

OpenTofu manages the existing CRS305-1G-4S+ at `10.1.0.254`.
The initial adoption used RouterOS 7.17.1 on November 12, 2026.
The device serial number is `HGW0A9T5001`.

The stack uses the existing Terramate, Task, R2, and 1Password workflow.
Its state key is `mikrotik/terraform.tfstate` in the `homelab-tfstate` bucket.
The credentials come from the **Mikrotik SFP Switch** item in the **Lab** vault.
The `.env.op` file contains references, not passwords.

## Configuration coverage

The stack contains 42 managed resources:

| Configuration | Resources |
| --- | ---: |
| Physical Ethernet and SFP ports | 5 |
| Bridges, bridge ports, and bridge VLAN membership | 7 |
| Storage VLAN interface | 1 |
| Interface lists and members | 6 |
| Management address and static routes | 3 |
| DNS and neighbor discovery | 2 |
| SNMP configuration and community | 2 |
| Identity, clock, note, and administrator metadata | 4 |
| IP services and SSH configuration | 9 |
| Default Hotspot and IPsec profiles | 2 |
| Disabled OpenVPN server | 1 |

The configuration preserves the disabled storage VLAN, the unused `sfp` bridge, and the existing management services.
The default route and the route to `10.1.1.0/24` both use `10.1.0.1`.
The default route came from the live API because the compact text export omitted it.
Resource references connect ports, bridges, interface lists, and the management address.

Dynamic routes, counters, link status, and the current clock time are runtime data.
Built-in interface lists remain part of RouterOS.
The administrator password stays outside resource configuration because RouterOS does not return it.
The stack manages the existing account metadata without resetting its password.

## Verify zero changes

From the repository root, run:

```sh
cd infra/stacks/mikrotik
task init
task check:no-changes
```

The check runs formatting validation, provider validation, and a full live plan.
It requires `tofu plan -detailed-exitcode` to return `0`.
It also checks all adopted resource addresses and rejects pending imports or deferred changes.
It does not disable refresh or target a subset of resources.
No resource uses `ignore_changes`.

The final output must contain:

```text
No changes. Your infrastructure matches the configuration.
Verified 42 managed resources: 0 to add, 0 to change, 0 to destroy.
```

The check saves its log, JSON plan, and result under the ignored `.local/` directory.
The result includes a timestamp and configuration hashes.
A failed check removes the previous result to prevent stale evidence.
Saved plans and local snapshots remain outside Git.

## Change configuration

1. Edit the relevant `.tf` file or `openvpn.json`.
2. Run `task plan`.
3. Review the saved plan.
4. Run `task apply` to apply that reviewed plan.

The apply task backs up remote state before and after the apply.
Every managed resource has `prevent_destroy` while its resource block remains present.
The initial adoption changed state only. It did not apply configuration to the switch.

## Repeat adoption after state loss

The current resources already exist in R2 state.
Normal operation does not require another import.

If state recovery is necessary, restore a state backup first.
If no usable backup exists, run `task import` after `task init`.
Then run `task check:no-changes` before any apply.

The adoption script checks the device serial number and the default workspace.
It rejects unexpected resource addresses and backs up existing state.
The IDs in `imports.json` refer to this device and can change after a reset.
This stack adopts the existing device; it is not a factory-reset provisioning procedure.

Provider 1.99.1 has several import limitations:

| Limitation | Adoption method |
| --- | --- |
| DNS has no importer | Read live DNS values and add its singleton binding to state. |
| Service imports return numeric IDs, but subsequent reads require names | Read each service and record its name as the state ID. |
| Ethernet imports omit the required `factory_name` field | Copy the verified live `default-name` into provider metadata. |
| Neighbor discovery uses a list importer for a singleton | Pass `*0` through the importer; the provider reads the singleton configuration. |
| OpenVPN uses named servers in RouterOS 7.17 | Use the REST provider and select writable fields through `.proplist`. |

The script imports 32 resources through the native importer.
It adopts the other 10 bindings from live GET requests and fills five Ethernet identity fields.
It preserves the state lineage and uses the normal locked `tofu state push` command without `-force`.
The subsequent plan refreshes every resource through its provider.

The RouterOS provider reports schema warnings for profile `default` flags and Hotspot `install-hotspot-queue`.
Those fields are absent from its resource schema.
The initial live values were `default=true` and `install-hotspot-queue=false`.
The configured profile attributes remain under management.

## Connections and credentials

The existing native API uses port 8728, and the REST API uses HTTP on port 80.
These connections are unencrypted and require the trusted management LAN.
The switch has no API TLS certificate, and SSH forwarding is disabled.
The adoption preserves those settings.

The pinned providers are `terraform-routeros/routeros` 1.99.1 and `Mastercard/restapi` 3.0.0.
The second provider manages only the disabled OpenVPN server.
Its credentials use the same 1Password item.
Neither provider requires credentials in Terraform variables or HCL.

## Local regression checks

From `infra`, run:

```sh
python3 -m unittest discover -s tests -v
```

These checks cover state adoption safeguards and rejection of incomplete or changing plans.
They require no router access or credentials.

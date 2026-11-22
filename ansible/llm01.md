# llm01

Observed over SSH as `victor` on 2026-11-15. `llm01` resolves through the existing
network DNS; the machine's transient hostname is `fedora` (no static hostname).

## Scope

`llm01.yml` reconciles the existing Fedora 43 Workstation installation and its
Halogen workload. It requires an existing `victor` account with UID 1000, sudo,
and SSH access. This is not a bare-metal installer or a complete home-directory
backup. No disk formatting, reboot, or OS upgrade is performed.

Managed state:

- Podman/crun/toolbox, AMD firmware and Vulkan drivers, SSH/firewall packages,
  and selected observed administration tools (package presence, not exact versions).
- Europe/Madrid timezone, console boot, masked sleep/hibernate/suspend targets.
- Kernel arguments `amd_iommu=off amdgpu.gttsize=126976 ttm.pages_limit=32505856`.
  Changed boot arguments take effect after a separately scheduled reboot.
- Persistent victor user manager and the exact captured user unit definitions.
- Enabled/running Halogen 0.18.5, serving port 8731 with GPU devices, host IPC,
  unlimited memlock, and `/home/victor/halogen-models` mounted into `/models`.
- Disabled/stopped LiveSync and real-estate dashboard, matching their observed state.

The launcher defaults to `peonist-ai/halogen-qwen3.8-flash-next`. Starting on a
fresh host can download large model files. Existing models included
`qwen38-flash-next-ngram.hgn`, `qwen38-flash-next-v2.hgn`,
`qwen38-flash-next-vision.hgn`, and a tokenizer directory. Model files are not
versioned here. The image is version-tagged as observed, not digest-pinned.

## Observed state outside management

- SELinux enforcing; FedoraWorkstation default firewall zone on eno1, with
  dhcpv6-client, samba-client and ssh services; TCP/UDP 1025–65535 allowed,
  forwarding enabled, masquerading disabled. The playbook enables firewalld
  but leaves its existing policy and NetworkManager profiles intact.
- Btrfs root/home, separate ext4 boot and EFI partition. Disk UUIDs and network
  configuration are intentionally not provisioned.
- victor UID/GID 1000, wheel membership, subordinate UID/GID range
  `524288:65536`; GPU render and kfd devices were world read/write.
- Installed kernel 6.19.8-200.fc43.x86_64, Podman 5.8.1, crun 1.25.1.
- Historical stopped/created AMD toolbox and llmfit containers are not recreated.
- Other desktop/default OS packages, SSH keys, credentials, application source,
  Python/Node environments, browser state and personal files are not managed.

Hermes no longer runs on llm01. Its leftover gateway and backup units are
excluded from this playbook; existing files on the server are left untouched.

The inactive service definitions reference `obsidian-vault`,
`real-estate-monitor`, and executables under `.local/bin`.
Restore those applications, environments and secret configuration from their
own backups before enabling these services. Copying unit files alone does not
rebuild those applications. No private keys or application secrets are in these
captured files.

## Run

From the repository root, with Ansible Core available and an authenticated
1Password CLI (including a service account configured outside this repository):

```bash
: "${LLM01_SSH_KEY_REF:?Set this to the 1Password reference for the SSH private key field}"
key_dir=$(mktemp -d)
chmod 700 "$key_dir"
trap 'rm -rf "$key_dir"' EXIT
op read "$LLM01_SSH_KEY_REF" > "$key_dir/key" || exit 1
chmod 600 "$key_dir/key"
ansible-playbook -i ansible/inventory.yml ansible/llm01.yml \
  --private-key "$key_dir/key" --ask-become-pass --check --diff
```

Remove `--check --diff` to apply. Applying changed launcher/unit files can restart
Halogen. Review the dry run first. SSH host-key verification remains enabled.

## Validation

Syntax check and bash syntax validation passed. Before excluding the obsolete
Hermes definitions, live check mode completed with
`ok=15 changed=0 failed=0 unreachable=0`. Syntax validation was repeated after
that exclusion. No apply or fresh-host rebuild was run.

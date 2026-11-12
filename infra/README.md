# Infrastructure stacks

Terramate generates shared configuration and runs commands across independent OpenTofu stacks.
Each stack has its own state, provider lock file, saved plan, and credentials.

```text
infra/
  .env.op                      Shared R2 settings and 1Password references
  mise.toml                    OpenTofu and Terramate versions
  Taskfile.yml                 Local checks across all stacks
  taskfiles/stack.yml           Shared init, plan, backup, and apply tasks
  scripts/                     Credential loader and R2 backup helper
  stacks/
    backend.tm.hcl             Shared R2 backend generator
    unifi/                     Existing gateway BGP stack
    proxmox/provider.tm.hcl     Provider generator for future Proxmox stacks
  templates/proxmox-vm/         VM stack template, excluded from orchestration
```

The repository-level `terramate.tm.hcl` sets the Terramate version constraint.
Only directories with a `stack {}` block are stacks.
The Proxmox template does not create or adopt any VMs until you copy it into a stack and apply a plan.

## Install tools

Install mise, Task, the 1Password CLI, Python 3.9 or later, and the AWS CLI.
From the repository root, run:

```sh
cd infra
mise trust
mise install
task list
task init:local
task validate
```

These checks require no R2 or provider credentials.
`init:local` downloads providers, so it requires network access on the first run.
The local checks permit uncommitted files.
State-changing commands retain Terramate's default safeguards.

## Work with a stack

From `infra`, select a stack by path:

```sh
mise exec -- terramate -C stacks/unifi run task init
mise exec -- terramate -C stacks/unifi run task plan
# Review the saved plan before this command.
mise exec -- terramate -C stacks/unifi run task apply
```

You can also run these tasks directly from the stack directory.
Direct Task commands do not use Terramate's Git safeguards.
The UniFi [runbook](stacks/unifi/README.md) covers import and BGP recovery.

For several stacks, select a directory or a tag:

```sh
mise exec -- terramate --tags=proxmox list
mise exec -- terramate --tags=proxmox run task init
mise exec -- terramate --tags=proxmox run task plan
```

After you commit changes, use `--changed` to select stacks relative to a Git revision:

```sh
mise exec -- terramate --git-change-base=HEAD~1 --changed list
```

Shared backend changes update generated files in every affected stack.
Stack `watch` lists cover shared tasks, scripts, credentials references, and tool versions.

## State and credentials

Each stack sets an explicit `global.state_key`, such as `proxmox/example/terraform.tfstate`.
Keep this key stable when you rename or move a stack.
Use a different key for each stack and use only the default OpenTofu workspace.

The tasks load `infra/.env.op` and the selected stack's `.env.op` through `op run`.
These files contain non-secret settings and 1Password references.
The [UniFi runbook](stacks/unifi/README.md#create-the-state-bucket) describes the shared R2 bucket setup.

The apply task backs up state before and after the saved plan runs.
A new stack can skip the first backup only when R2 returns HTTP 404 for its state object.
UniFi requires existing state and cannot skip this backup.
Permission errors and other backup errors stop the apply task.
If the final backup fails, inspect the state before you retry because the apply can already have succeeded.

Backups use `backups/<stack-key-prefix>/<timestamp>-<uuid>.tfstate` in the same bucket.
Run state-changing commands from one session at a time.
Backups occur separately from OpenTofu's locked state updates.

## Add a Proxmox VM stack

The template clones an existing cloud-init VM template on the same Proxmox node.
It uses DHCP and SSH public keys.
The clone inherits its disks from the template.
The guest agent is disabled by default. Enable `vm.guest_agent` only if the template starts `qemu-guest-agent`.

Choose a node, datastore, existing template ID, and unused VM ID.
From `infra`, create the stack without generation until its state key exists:

```sh
mise exec -- terramate create --no-generate --name example --tags=proxmox,vm \
  --watch=/infra/.env.op,/infra/mise.toml,/infra/taskfiles/stack.yml,/infra/scripts/with-env.sh,/infra/scripts/backup_state.py \
  stacks/proxmox/example
cp -R templates/proxmox-vm/. stacks/proxmox/example/
cat > stacks/proxmox/example/globals.tm.hcl <<'EOF'
globals {
  state_key = "proxmox/example/terraform.tfstate"
}
EOF
cp stacks/proxmox/example/.env.op.example stacks/proxmox/example/.env.op
cp stacks/proxmox/example/terraform.tfvars.example stacks/proxmox/example/terraform.tfvars
```

Replace the example endpoint and 1Password reference in `.env.op`.
The referenced credential must contain the full `user@realm!token-id=secret` API token.
Use a trusted TLS certificate and a token with access to the source template and target resources.
See the [provider authentication guide](https://github.com/bpg/terraform-provider-proxmox/blob/v0.122.0/docs/index.md).

Replace the example values in `terraform.tfvars`, including the SSH public key.
The local variables file stays outside Git.
Then run:

```sh
task fmt
task generate
task --dir stacks/proxmox/example init:local
task --dir stacks/proxmox/example validate
```

Commit the stack definition, `.env.op` references, generated `.tf` files, and provider lock file.
Then run `init` and `plan` for that stack, review the plan, and run `apply`.
For an existing VM, import its resource and review the plan before any apply.
See the [VM resource documentation](https://github.com/bpg/terraform-provider-proxmox/blob/v0.122.0/docs/resources/virtual_environment_vm.md).

For other providers, create a stack below `stacks/` and set its state key.
Add provider requirements and resources, then include `taskfiles/stack.yml` at the correct relative path.
Add the shared files to its `watch` list, as shown in the example.
Only the `proxmox/` subtree inherits the Proxmox provider.

Edit `.tm.hcl` files to change generated configuration, then run `task generate`.
Commit the generated files so reviewers can inspect the resulting OpenTofu configuration.
See the [Terramate guide](https://terramate.io/docs/cli/getting-started) for stack selection and code generation.

## Migration from `infra/unifi`

The UniFi stack now lives at `infra/stacks/unifi`.
Its state key remains `unifi/terraform.tfstate`, and its resource address remains `unifi_bgp.gateway`.
The move requires no state migration or re-import of an already imported resource.
Run `task init` from the new directory, then create and review a fresh plan.

## Workflow regression checks

Run `python3 -m unittest discover -s tests -v` from `infra`.
These tests replace provider, credentials, and R2 commands with local stubs.

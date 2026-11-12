# UniFi BGP

OpenTofu manages the gateway's BGP configuration from `bgp.conf`.
The gateway is `10.1.0.1`, with local ASN `65000` and site `default`.
The file preserves the live peer groups and `remote-as external` settings.
It includes peers `10.1.0.11` and `10.1.0.12`, which were missing from the old local file.

State is stored in Cloudflare R2 at `s3://homelab-tfstate/unifi/terraform.tfstate`.
The S3 backend uses a lock object to prevent concurrent state changes.
Credentials, local state files, and saved plans are excluded from Git.
Include `.env.op` and the provider lock file, `.terraform.lock.hcl`, in Git.
`.env.op` contains only non-secret settings and 1Password references.

## Create the state bucket

Create the bucket before initializing OpenTofu.
Manage the bucket separately from this configuration, because it stores this configuration's state.

1. Open **R2 Object Storage** in the existing Cloudflare account.
2. Create a private bucket named `homelab-tfstate` with **Standard** storage.
3. Keep public access disabled.
4. Create an R2 API token with **Object Read & Write** permissions for this bucket only.
5. Save an **API Credentials** item named `homelab-r2-state` in the 1Password **Lab** vault.
6. Store the Access Key ID in `username` and the Secret Access Key in the concealed `credential` field.

The backend needs the S3 Access Key ID and Secret Access Key, not the Cloudflare bearer token.
The DNS API token cannot access R2.

R2 Standard includes 10 GB of storage, one million Class A operations, and ten million Class B operations each month.
This state should fit within the [free allowance](https://developers.cloudflare.com/r2/pricing/).
The allowance is shared with other R2 usage in the account; usage above it is billed.

## Configure authentication

Install `mise`, Task, the 1Password CLI, Python 3, and the AWS CLI.
The AWS CLI connects to R2; no AWS account is required.

From the repository root:

```sh
cd infra/unifi
mise trust
mise install
```

The repository's `.env.op` contains the account settings and references to the existing 1Password items.
No local configuration copy is required.
Update `.env.op` when those settings or references change, and commit the changes.
The tasks automatically use `op run` to resolve `.env.op` references into environment variables.
Run `task plan` directly and approve the 1Password access prompt when it appears.
Do not put credentials in HCL, backend arguments, or committed files.

The example uses the existing Site Manager key through Cloud Connector.
It selects the Home console explicitly and keeps TLS certificate verification enabled.
The key is valid for Site Manager; the local gateway does not accept it.

For direct local access, set `UNIFI_CLOUD_CONNECTOR=false`.
Use a UniFi Network API key accepted by the local gateway, or a dedicated local administrator account.
For username/password authentication, remove `UNIFI_API_KEY` and set `UNIFI_USERNAME` and `UNIFI_PASSWORD` to 1Password references.
The provider ignores username/password settings when an API key is present.

For a gateway with an untrusted local certificate, set `UNIFI_INSECURE=true` only after confirming its identity.
This setting disables certificate verification.

The provider also supports Site Manager keys through `UNIFI_CLOUD_CONNECTOR=true`.
Set `UNIFI_HARDWARE_ID` to the intended console when using this mode.
Cloud Connector ignores the local API URL and uses verified HTTPS through `api.ui.com`.
See the [provider authentication documentation](https://github.com/ubiquiti-community/terraform-provider-unifi/blob/v0.65.0/docs/index.md).

## Adopt the existing configuration

Run these commands from `infra/unifi`:

```sh
task init
task import
task plan
```

Import reads the existing gateway configuration into R2 state without changing BGP.
It then creates a backup of the imported state.
The first plan must show **no changes** before routine management starts.
If it proposes changes, compare the live configuration with `bgp.conf` and resolve the differences first.
Do not apply a plan merely to complete the import.

`prevent_destroy` blocks planned deletion of the BGP resource while that lifecycle rule remains in the configuration.
The plan task also requires the gateway resource to exist in state.
It checks state after loading credentials and reports backend errors without replacing them with an import message.

## Change BGP

1. Edit `bgp.conf`.
2. Generate the saved plan:

   ```sh
   task plan
   ```

3. Review the proposed gateway changes.
4. Apply the reviewed plan:

   ```sh
   task apply
   ```

`task apply` applies `unifi.tfplan` without another approval prompt.
It creates state backups before and after the apply.
If the initial backup fails, the apply stops.
If the final backup fails, the gateway change may already have succeeded; inspect the state before retrying.
Generate a new plan after editing the configuration again.

Use the default OpenTofu workspace.
Run state-changing commands from one session at a time.
Backups are separate operations from OpenTofu's locked state updates.

## Backups and recovery

R2 does not support S3 bucket versioning.
The backup task copies the current remote state to a unique object under `backups/unifi/`:

```sh
task backup
```

These copies provide history, but they remain in the same bucket with the same credentials.
Direct `tofu` commands bypass the task's backup steps.
Do not apply a bucket lifecycle rule to the active `unifi/` prefix.

To recover state, stop other state-changing sessions and download the required backup to the ignored `.local/` directory.
Compare its lineage, serial, and resource ID with the current state from `tofu state pull`.
Use `tofu state push` with normal lineage and serial checks after reviewing the recovery.
If those checks reject an older snapshot, investigate before considering a forced restore.
Run a new plan after recovery; restoring state does not restore the gateway's BGP configuration.

For BGP rollback, restore the required Git revision of `bgp.conf`, then review and apply a new plan.

## Local checks

Provider validation does not require gateway or R2 credentials:

```sh
mise exec -- tofu init -backend=false
task validate
```

Run `task init` before importing, planning, or applying; it loads credentials from 1Password automatically.
Backend settings follow Cloudflare's [remote state guide](https://developers.cloudflare.com/terraform/advanced-topics/remote-backend/).

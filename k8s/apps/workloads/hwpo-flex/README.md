# HWPO Flex

HWPO Flex is a user service on the management cluster. The service stores progress data on NFS.

This component is a workload component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `hwpo-flex` namespace.

## Image

The management overlay pins `zot.apps.fondevilla.io/hwpo-flex:d8580645eafaa164991383c0ce195d4dc098e481`.

The `Build hwpo-flex image` workflow (`.github/workflows/hwpo-flex-image.yml`) builds the
application image for `linux/amd64` and pushes only the full application commit SHA tag. The
workflow only builds and publishes. It never merges or deploys.

The workflow never overwrites an existing tag. Before a push it queries the exact manifest it
would write through the OCI Distribution API. The push runs only when that query succeeds and
returns HTTP 404 with a well-formed OCI error document whose entries are all recognized
unknown-manifest codes (`MANIFEST_UNKNOWN` or `NAME_UNKNOWN`). A valid OCI or Docker image
manifest response means the tag exists and the run is a no-op. Every other outcome, including
transport, authentication, encoding, configuration, and malformed or mixed responses such as
proxy error pages, fails the run closed and writes no push authorization. GitHub concurrency
serializes this repository's dispatches for the same tag. The check cannot serialize unrelated
writers: a different publisher can create the same tag between the check and the push.

No secret appears in job-wide environment variables. The source slug reaches only the validate
and fetch steps, the source token only the fetch step, and the registry credential pair only the
login and registry query steps. The checkout, build, push, and cleanup processes receive no raw
secrets.

The private source slug, the source token, and the private Dockerfile content never appear in
the public job log. All git and Docker output goes to a runner-local log on the ephemeral
runner. The workflow uploads no artifacts and uses no shared caches.

### Prerequisites

- The `hwpo-flex-publish` protected GitHub environment. The job declares this environment.
  Configure a deployment branch rule that allows only `main` and no tags.
- Environment secrets on `hwpo-flex-publish`:
  - `HWPO_FLEX_SOURCE_REPOSITORY`: the `owner/repo` slug of the private application
    repository. The workflow never hardcodes or commits that slug.
  - `HWPO_FLEX_SOURCE_TOKEN`: a least-privileged read-only token for the private application
    repository. The workflow fetches the exact SHA with an ephemeral, process-scoped auth
    header. It never puts the token in a URL and never writes git credentials to disk.
  - Optional paired registry secrets: `HWPO_FLEX_REGISTRY_USERNAME` and
    `HWPO_FLEX_REGISTRY_PASSWORD`. Set both or neither. The cluster currently pulls images
    anonymously. The workflow injects them only after a successful build, into a job-private
    `DOCKER_CONFIG`, and passes the password to `docker login` only through stdin. The first
    step after checkout creates that `DOCKER_CONFIG` directory with mode `0700` and a
    `config.json` with mode `0600` that holds an empty `auths` entry for the target registry.
    The empty entry stops Docker from auto-detecting native credential helpers, so anonymous
    runs cannot read a previous machine login. Because the isolated `DOCKER_CONFIG` also
    ignores a docker context stored in the user config, the runner must reach its Docker
    daemon through the default `/var/run/docker.sock` or through `DOCKER_HOST`.
    Anonymous publishing relies on the existing internal-network reachability of the Zot
    registry, whose configuration deliberately permits anonymous access. Configuring these
    secrets on this runner does not restrict other network clients. Operators who want
    exclusive publisher access must deny anonymous writes in the registry's server-side
    configuration and set these secrets to a credential scoped to `hwpo-flex`. That
    server-side change is a separate decision, not a prerequisite for the current anonymous
    mode.
- A Docker-capable ephemeral runner or Actions Runner Controller scale set with connectivity
  to `zot.apps.fondevilla.io`. The runner image must provide `git`, `docker`, `curl`, and
  `python3`. The helper uses `python3` to validate registry response documents during the tag
  check. A missing prerequisite fails the run closed. The runner labels come from the
  `HWPO_FLEX_IMAGE_RUNNER_LABELS` repository variable, evaluated when the job is scheduled.
  The default is the single unique label `["hwpo-flex-publisher"]`. There is no generic
  self-hosted fallback. The general CI runners currently configured through Actions Runner
  Controller in the management cluster have no Docker or registry connectivity and do not meet
  these publisher requirements.
- A runner supervisor that enforces which jobs may run on that runner and reach the private
  registry. This is a personal repository. GitHub offers self-hosted runner groups only to
  organizations and enterprises, so no workflow-scoped runner group can gate this job.
  Labels, the environment branch rule, and the workflow `if:` guard are defense in depth,
  not an enforceable gate on their own. See "Runner access enforcement" below.

### Runner access enforcement

Workflow YAML and runner labels alone cannot bind a job to a runner. Do not rely on
just-in-time labels, one-shot runner registration, webhook-triggered pre-provisioning alone,
a writable workflow environment, or stock Actions Runner Controller label filters. Any
enforceable gate must live outside GitHub, on runner infrastructure you control. The
supervisor design below is one enforceable example, not the only possible mechanism, and
not something this repository provisions. It binds each single-use runner to the job it was
actually assigned.

1. A trusted supervisor owns runner registration for the publisher scale set. Each runner
   accepts exactly one job, provides an ephemeral Docker daemon per run, and is destroyed
   afterward. There is no persistent shared daemon.
2. When the supervisor assigns a job to a runner, it records the runner identity and the
   assigned job. Before it starts any job step, it fetches that job's metadata from GitHub
   through the Actions API, authenticated with the supervisor's own credential, never the
   job token. It requires all of the following:
   - `repository.full_name` is `vFondevilla/k8s-homelab`
   - the workflow path is `.github/workflows/hwpo-flex-image.yml`
   - the run's `head_branch` is `main` and the run's `event` is `workflow_dispatch` or
     `repository_dispatch`
   - the job's assigned runner name matches the single-use runner identity the supervisor
     launched
   On any mismatch or API failure, the supervisor destroys the runner and the job never
   runs.
3. Network policy denies all egress from runner workloads by default. The supervisor opens
   egress to `zot.apps.fondevilla.io` only for an admitted job. Private registry credentials
   are reachable only inside an admitted run.

Official references:

- Secure use of Actions and self-hosted runner hardening:
  <https://docs.github.com/en/actions/reference/security/secure-use>
- The `workflow_job` webhook event:
  <https://docs.github.com/en/webhooks/webhook-events-and-payloads#workflow_job>
- Actions API, "Get a job for a workflow run":
  <https://docs.github.com/en/rest/actions/workflow-jobs#get-a-job-for-a-workflow-run>
- Runner groups are an organization and enterprise feature:
  <https://docs.github.com/en/rest/actions/self-hosted-runner-groups>

### Manual build

Run the workflow from the Actions tab on the `main` branch of `vFondevilla/k8s-homelab`.
Enter the full 40-character lowercase commit SHA of the application source to build.

### External dispatch

Send a `repository_dispatch` event of type `build-hwpo-flex-image` with the application SHA.
Quote the payload field so that zsh does not treat `[sha]` as a glob. The quoted form works
in both bash and zsh:

```sh
sha=d8580645eafaa164991383c0ce195d4dc098e481
gh api repos/vFondevilla/k8s-homelab/dispatches \
  -f event_type=build-hwpo-flex-image \
  -f "client_payload[sha]=$sha"
```

The workflow runs only on the `main` branch of `vFondevilla/k8s-homelab`. It rejects any SHA
that is not a full lowercase 40-character hexadecimal string before it fetches source.

## Dependencies

The ingress uses the Cilium ingress class. It also uses the `letsencrypt-prod` ClusterIssuer.

The persistent volume uses the NFS server at `10.254.0.3`.

The directory `/mnt/flash/k8s_static_pv/hwpo-flex` must exist on that server.

## Persistent resources

The PersistentVolume is `hwpo-flex-progress-pv`. Its reclaim policy is `Retain`.

The PersistentVolumeClaim is `hwpo-flex-progress` in the `hwpo-flex` namespace.

Preserve both resource names and UIDs during a source-path migration.

## Render

Operate this command from the repository root:

```sh
kustomize build k8s/apps/workloads/hwpo-flex/overlays/management
```

## Migration constraint

Preserve the `in-cluster-hwpo-flex` Application name during a source-path migration.

Synchronize this component without pruning. Then make sure that the PV and PVC remain Bound.

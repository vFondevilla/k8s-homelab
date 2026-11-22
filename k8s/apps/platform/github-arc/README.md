# GitHub Actions Runner Controller

The management overlay installs ARC controller and scale-set charts at `0.15.1` and the required CRDs in `arc-system`. The organization scale set registers only with `https://github.com/cloud-viking-io`. A separate Argo CD ApplicationSet discovers the repositories in the `vFondevilla` GitHub App installation and creates one scale-set release per active repository. Repository names and IDs are obtained at runtime and are not stored in this public repository.

## GitHub setup

Create two GitHub Apps and store credentials in 1Password. Install the `cloud-viking-io` app in that organization. Install the `vFondevilla` app on the personal account with **all repositories** selected. Discovery verifies the installation account is the `vFondevilla` user and that its numeric account ID is present. Selected-repository installations are rejected because the requested coverage is every personal repository. Installations must include metadata for each repository.

The organization app needs organization self-hosted runner administration read/write and metadata read-only. The personal app needs repository administration read/write and metadata read-only. Do not grant contents, workflows, or Actions administration permissions. ARC needs runner administration to create ephemeral runners; the runner pods receive no GitHub App credentials and no Kubernetes API token.

Create a GitHub runner group named `cloud-viking-io` in the organization, assign the desired organization repositories to that group, and allow the group to be used by Actions. This group name is configured in the scale-set chart. The account-level scale sets use GitHub's `Default` runner group. Keep personal account repository access limited by the App installation selection. A public repository can use a private self-hosted runner only when its runner group explicitly permits that repository; never expose a private runner group to arbitrary public repositories.

Create these 1Password items and fields before enabling the overlay:

| Item | Fields |
| --- | --- |
| `GitHub ARC cloud-viking-io` | `app_id`, `installation_id`, `private_key` |
| `GitHub ARC vFondevilla` | `app_id`, `installation_id`, `private_key` |
| `ARC Argo plugin` | `token` |

Use the App private key PEM as `private_key`; the plugin token must be a random 32-byte or longer value. External Secrets places org and personal App credentials in separate runner namespaces, and the personal App credentials are separately copied to the discovery namespace. The Argo plugin token is stored in an Argo-labelled Secret for the ApplicationSet controller and projected into the discovery namespace from the same 1Password item. Discovery reads the projected token file on every request, so External Secrets rotation takes effect without a pod restart. No credential value belongs in Git.

The discovery service verifies the App installation's account login, numeric account ID (`10423165`), type, and `repository_selection: all` on both `/app/installations/{id}` reads: before minting a token and after reading the complete inventory. The token response and each `/installation/repositories` page may omit `repository_selection`; if present, it must be `all`. Discovery makes no `repository_ids` restriction in the token request and requests metadata read permission only. It checks `total_count` across every unique repository before filtering archived or disabled repositories. For a multi-page listing, it requires a second independently complete listing with the same repository IDs, names, and archived/disabled state before returning results. Any authentication, HTTP, malformed response, transfer, duplicate ID, unstable count or inventory, missing/repeated page, or pagination failure returns an error to the ApplicationSet generator. It does not convert failures into an empty list or reconcile partial results. A valid all-repositories installation with zero repositories returns an empty list. The repeated checks narrow the window for an installation change; they cannot make the remote inventory atomic after a response has been returned. GitHub repository names may contain dots and underscores. The generator runs every five minutes. The pinned Python slim image includes OpenSSL; discovery uses its `openssl dgst` command for RS256 signing rather than parsing private-key ASN.1 itself.

ApplicationSet `applicationsSync: sync` permits template changes and rename updates as well as deletions. For planned decommissioning of one personal repository, archive that repository while it remains authorized; discovery then removes its generated Application. ARC 0.15.1 removes the listener and ephemeral runner set first, but can retain an `AutoscalingRunnerSet` finalizer when GitHub returns a cleanup error other than 404. If a scale set is Terminating, inspect its metadata and status, controller logs, and the repository's GitHub Actions runner settings before taking action:

```sh
kubectl get autoscalingrunnersets.actions.github.com -n arc-runners-vfondevilla
kubectl get autoscalingrunnerset.actions.github.com <scale-set-name> -n arc-runners-vfondevilla -o jsonpath='{.metadata.deletionTimestamp}{"\n"}{.metadata.finalizers}{"\n"}{.status}{"\n"}'
kubectl get pods -n arc-system
kubectl logs -n arc-system <scale-set-controller-pod> --all-containers=true --since=30m
```

Check the matching GitHub repository's **Settings → Actions → Runners** for remaining scale sets or runners.

### Recovering one personal repository

If recovery may require restored App authorization or unarchiving, temporarily hold only that repository out of discovery by adding this post-selector to the same generator mapping as `plugin` in `k8s/argocd/applicationsets/management/github-arc-personal.yaml`:

```yaml
    - plugin:
        configMapRef:
          name: arc-personal-repositories
        requeueAfterSeconds: 300
      selector:
        matchExpressions:
          - key: repoID
            operator: NotIn
            values: ["123456789"]
```

Replace the example ID with the affected repository's numeric ID; do not add the `vf-` prefix. Keep the real ID in the authorized GitOps change mechanism and do not publish it in this public README. After applying the temporary selector, verify that the exact numeric ID and `NotIn` operator are present on the live ApplicationSet `github-arc-vfondevilla` in namespace `argocd`:

```sh
kubectl -n argocd get applicationset github-arc-vfondevilla -o yaml
```

Inspect `spec.generators[...].selector.matchExpressions` for `key: repoID`, `operator: NotIn`, and the affected numeric ID in `values`.

Use the recovery branch that matches the current state:

1. **Discovery cannot read the installation because authorization was revoked before the generated Application was deleted:** verify the live selector as above before restoring credentials or App authorization. With the hold still active, restore all-repositories authorization. Let the next successful inventory run trigger pruning, then verify the generated `vf-<id>` Application is deleted or deleting. Do not wait for Application deletion before restoring access in this branch.
2. **Access is intact, but archiving blocked remote deregistration:** verify the live selector and confirm pruning has begun before temporarily unarchiving the repository. This lets ARC retry remote cleanup while discovery continues to exclude the repository.

In either branch, keep the selector through every cleanup poll until local ARC resources and remote registrations are cleaned up or have been manually addressed while properly authorized. Inspect the `AutoscalingRunnerSet`, listener and runner resources, and check GitHub's runner settings. Do not strip finalizers as routine recovery. For a smoke test, keep the repository unarchived and remove the selector only after cleanup is verified, to re-enroll it. For permanent decommissioning, rearchive it before removing the selector. Deleting the generated Application alone is temporary because discovery recreates it while the repository remains active.

### Removing the personal installation

For full-installation decommissioning, remove or disable the personal ApplicationSet through GitOps and wait for cascading Kubernetes cleanup. Verify GitHub runner registrations are removed before revoking the App installation. If access was revoked first, restore all-repositories authorization while holding affected repositories out of discovery, then let a successful inventory trigger pruning. Kubernetes pruning alone does not guarantee GitHub-side cleanup.
## Runner behavior and security

Use `runs-on: cloud-viking-io` for organization jobs. Personal repository scale sets use `runs-on: vf-<GitHub repository numeric ID>`; the numeric ID provides a short, stable, unique label without publishing repository names. The org scale set allows up to five simultaneous jobs; each personal scale set allows up to three. All set `minRunners: 0`, so there are no idle runner pods. Jobs run on ephemeral ARC-managed pods.

Runner service accounts disable token automount. Runner pods use UID/GID 1001, drop Linux capabilities, deny privilege escalation, and use the runtime default seccomp profile. Listener pods receive their own explicit Restricted-compatible settings. The ARC namespaces enforce Baseline Pod Security because the scale-set manager creates helper pods; runner and listener pods use explicit restricted contexts. Runner namespaces deny ingress and use Kubernetes NetworkPolicies to allow DNS only to kube-dns on UDP/TCP 53 and public IPv4/IPv6 destinations only on TCP 443. IPv4 RFC1918, loopback, link-local, carrier-grade NAT, and metadata ranges are excluded. IPv6 uses `2000::/3` with `2001:db8::/32` explicitly excluded; ULA and link-local ranges are outside the allowed CIDR. No additive runner Cilium allow policy is installed. CI egress is a policy intent and is not runtime verified here. Jobs that need private network services or Docker-in-Docker/privileged mode are intentionally unsupported. These restrictions depend on Cilium and Kubernetes NetworkPolicy enforcement.

### App private-key rotation

For either GitHub App, add the replacement private key in GitHub while the old key remains valid. Update the matching 1Password item's `private_key`, then wait for its ExternalSecret to report Ready and for the source Secret's `resourceVersion` to change. The org and personal source Secrets live in `arc-runners-cloud-viking` and `arc-runners-vfondevilla`; the personal App Secret is also synchronized to `arc-discovery`. ARC copies runner credentials into managed listener configuration Secrets in `arc-system`. Each `AutoscalingListener` manages a bare Pod with the same name, not a Deployment. After source Secret sync, allow the listener configuration Secret to refresh and its Pod to be recreated. If it does not reconcile, trigger the affected resource by updating a harmless annotation: `kubectl annotate autoscalinglistener.actions.github.com <listener-name> -n arc-system rotation-check="$(date +%s)" --overwrite`. Do not print Secret contents. Example checks:

```sh
kubectl get externalsecret arc-cloud-viking-io-app -n arc-runners-cloud-viking
kubectl get externalsecret arc-vfondevilla-app -n arc-runners-vfondevilla
kubectl get externalsecret arc-vfondevilla-discovery-app -n arc-discovery
kubectl get secret arc-cloud-viking-io-app -n arc-runners-cloud-viking -o jsonpath='{.metadata.resourceVersion}{"\n"}'
kubectl get secret arc-vfondevilla-app -n arc-runners-vfondevilla -o jsonpath='{.metadata.resourceVersion}{"\n"}'
kubectl get secret arc-vfondevilla-discovery-app -n arc-discovery -o jsonpath='{.metadata.resourceVersion}{"\n"}'
kubectl get autoscalinglisteners.actions.github.com -n arc-system
kubectl get pods -n arc-system
```

Check the affected `AutoscalingListener` and its same-named Pod in `arc-system`; verify its managed configuration Secret has refreshed before the Pod is recreated. Do not restart discovery: it reads the projected personal App credential files for each request. Verify discovery succeeds where applicable, then dispatch the corresponding authorized smoke job and confirm it succeeds. Check the synchronized credential Secrets and successful operation before revoking the old key.

ARC runner images are pinned to `2.338.2`. Review and update this version monthly, or sooner when GitHub publishes a security update. Both organization and personal runner templates must be updated together.

With zero idle runners, the controller, discovery service, and scale-set controllers stay running; runner pods are created only for jobs. At the configured caps, the cluster can run five organization jobs plus three jobs for every installed personal repository. Review node CPU/memory capacity and GPU requirements before installing the personal App on all repositories.

## Smoke verification

1. Confirm the three 1Password items synchronize to the intended namespaces and that each ExternalSecret reports Ready.
2. Check the controller deployment is available and ARC CRDs exist: `kubectl get crd | rg actions.github.com`.
3. Check the `cloud-viking-io` scale set appears in organization runner settings and personal scale sets appear only for installed repositories.
4. For a personal smoke run, copy `.github/workflows/arc-smoke-personal.yml` from this repository into a personal `vFondevilla` repository covered by the App, commit it, then run its `ARC personal repository smoke` workflow. For an organization smoke run, create `.github/workflows/arc-smoke-org.yml` in a `cloud-viking-io` repository where the `cloud-viking-io` runner group is enabled, commit the following workflow, then run `ARC organization smoke` there. The org workflow is an example only; it cannot run from this personal homelab repository. Both jobs only print the repository name and runner identity.

   ```yaml
   name: ARC organization smoke
   on:
     workflow_dispatch:
   jobs:
     smoke:
       runs-on: cloud-viking-io
       steps:
         - name: Confirm organization runner
           run: |
             echo "Repository: $GITHUB_REPOSITORY"
             echo "Runner: $RUNNER_NAME"
   ```
5. From an authorized disposable runner job, verify DNS and public HTTPS work while connections to cluster/service/private/link-local/metadata addresses fail.
6. To smoke-test prune and re-enroll behavior without changing the all-repositories installation, use a disposable personal repository. Archive it and wait for discovery to prune its Argo Application. If ARC needs restored authorization or the repository unarchived to finish cleanup, follow the temporary selector hold sequence above and remove the selector only after cleanup is verified. For permanent individual decommissioning, archive the repository while it remains authorized, diagnose any Terminating scale set, and follow the same hold sequence if cleanup requires restoring authorization. Do not revoke or deselect the repository for this test.

Run the repository discovery checks with `python3 -m unittest discover -s k8s/apps/platform/github-arc/overlays/management/tests -v`.

The personal ApplicationSet and the management overlay are intentionally active only through the management Argo tree. Do not add the ARC overlay to tenant or VPS discovery.

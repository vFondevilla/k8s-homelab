# Hermes Agent VM

The management overlay manages the existing Hermes VM in the `kubevirt` namespace.
It includes the VM, root DataVolume, LoadBalancer Service, SSH public-key Secret,
and a management-only TLS Ingress for the web dashboard and API.

## Argo CD

The management ApplicationSet discovers `overlays/management` and creates `in-cluster-hermes-agent`.
Automatic sync and self-healing are enabled. Automatic pruning is disabled for this stateful workload.
The DataVolume also has `Prune=false,Delete=false` to preserve its disk when Argo removes resources or deletes an Application.

KubeVirt manages the running VirtualMachineInstance. CDI manages the root PersistentVolumeClaim.
The manifests retain the existing resource names, namespace, disk source, and MAC address.

## Render and validate

From the repository root:

```sh
kustomize build k8s/apps/workloads/hermes-agent/overlays/management
kubectl --context homelab apply --dry-run=server -k k8s/apps/workloads/hermes-agent/overlays/management
```

## Access and storage

- SSH: `ubuntu@hermes.fondevilla.io`
- VM: `kubevirt/hermes-agent`
- Root disk: `kubevirt/hermes-agent-rootdisk`, on `nfs-client`
- Public keys: `kubevirt/hermes-agent-ssh`, synchronized through the QEMU guest agent
- Hindsight database: [separate CNPG component](../hindsight/README.md)

Changes to the VM template can require a restart. Argo synchronization does not perform that restart.

Reference: [Argo CD resource retention](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/).

## HTTPS web and API

- Web dashboard/chat: `https://hermes.apps.fondevilla.io/`
- OpenAI-compatible base URL: `https://hermes.apps.fondevilla.io/openai/v1`
- API health: `https://hermes.apps.fondevilla.io/openai/health`
- Existing project: `https://hermes.apps.fondevilla.io/inmobiliaria/`
- Existing SSH/LoadBalancer hostname `hermes.fondevilla.io` is unchanged.

```text
Client -- HTTPS --> Cilium Ingress (cert-manager TLS + External-DNS)
                    --> kubevirt/hermes-agent Service, port http (80)
                    --> KubeVirt masquerade networking --> guest Caddy :80
                        /openai/* --> strip /openai --> 127.0.0.1:8642 (API bearer key)
                        /inmobiliaria/* --> 127.0.0.1:8765 (existing project)
                        other paths on Hermes host --> 127.0.0.1:9119 (dashboard login)
```

The dashboard has its own `/api/*` and WebSocket routes; do not redirect them to
the OpenAI API. Caddy forwards WebSocket upgrades and streams API responses.
This uses one hostname and paths, not separate visible ports or API subdomains.

**Do not create an EndpointSlice for `10.0.2.2`.** That is the guest-side
masquerade address, not an established cluster-routable backend. The existing
Service already selects the VM launcher pod. No VM template/disk restart is
needed for this Ingress change. Do not expose listener ports 8642/9119 directly.

### Security and deployment boundary

Argo installs only the Kubernetes resources. It does **not** install files,
credentials, services or application builds inside this existing VM. The
`guest/` directory contains reviewed guest configuration and a routing test;
it is deliberately not an additional Kustomization resource directory.

Configure and test authentication inside the VM **before** merging/syncing the
Ingress. A backend that is missing remains a 502, not a usable deployment.
The dashboard is an administrative surface: it can edit credentials and run
agent tools. An API bearer key also grants powerful agent access.

- The supplied password-provider option is for this trusted homelab LAN/VPN
  only. Do not make it Internet-reachable with basic login alone.
- For Internet access use supported OIDC (public PKCE client, authorize only
  intended users), or put the entire service behind a separately verified VPN.
- Cilium terminates TLS. Ingress-to-guest traffic is HTTP; this is not end-to-end
  encrypted transport. Do not assume private addressing protects that hop.
- Never place real credentials in this public repository or a ConfigMap.
  Keep the guest env file outside Git; store the source secrets in 1Password.
  External Secrets into Kubernetes alone will not configure a VM guest.
- Dashboard session/password credentials and the API key are separate. No
  browser CORS wildcard or ingress authentication-bypass annotations are used.

### Guest setup (run as ubuntu on the VM)

1. Check installed `hermes serve --help`, `hermes dashboard --help`, and the
   [dashboard](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard)
   and [API](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server)
   docs. The dashboard/backend and messaging/API gateway are separate processes.
2. Create `~/.config/hermes-http/` with mode `0700`. Copy
   `guest/access.env.example` to `~/.config/hermes-http/access.env`, mode `0600`.
   Fill it privately, not in chat or shell command history. Use a unique random
   API key and 32+ bytes of random dashboard signing secret. Generate the scrypt
   password hash using `plugins.dashboard_auth.basic.hash_password` in the
   installed Hermes Python environment, with the password supplied via
   `getpass.getpass()` rather than a literal command argument. Alternatively
   supply OIDC issuer/client ID and register the exact callback documented in
   the example. Do not leave empty or placeholder credentials.
3. Keep `HERMES_DASHBOARD_PUBLIC_URL=https://hermes.apps.fondevilla.io`. This
   engages the dashboard auth gate even though its listener is loopback-only,
   and allows the exact Host/WebSocket Origin behind Caddy. Do not use
   `--insecure`, disable auth, or set a wildcard origin. Remove conflicting
   duplicate settings from existing configuration only after review.
4. Build the web assets using the installed release's supported build workflow.
   A first `hermes dashboard --no-open` can build them automatically; stop that
   foreground process after building, before starting the service. Ensure the
   TUI dependencies/build work too if using the embedded Chat tab.
5. Install the service and drop-in from this component (from the repository root):

   ```sh
   install -d -m 700 ~/.config/systemd/user/hermes-gateway.service.d
   install -m 644 k8s/apps/workloads/hermes-agent/guest/hermes-web.service \
     ~/.config/systemd/user/hermes-web.service
   install -m 644 k8s/apps/workloads/hermes-agent/guest/hermes-gateway-http.conf \
     ~/.config/systemd/user/hermes-gateway.service.d/http.conf
   systemctl --user daemon-reload
   systemctl --user enable --now hermes-web.service
   # Restart only after the current Telegram/agent turn has finished:
   systemctl --user restart hermes-gateway.service
   ```

   The existing gateway owns the API adapter. Do not launch a second gateway
   with the same platform credentials. The drop-in requires the private env
   file; it does not silently ignore a missing file. Starting the web service
   does not itself start the API adapter.
6. Before installing `guest/Caddyfile`, compare it with `/etc/caddy/Caddyfile`,
   back up the latter and preserve any newly added project routes. This version
   preserves the previously recorded `/inmobiliaria` route and old project index.
   Validate the candidate, install it with sudo, then reload (not restart) Caddy:

   ```sh
   caddy validate --config k8s/apps/workloads/hermes-agent/guest/Caddyfile --adapter caddyfile
   # After backing up and reviewing /etc/caddy/Caddyfile:
   sudo install -m 644 k8s/apps/workloads/hermes-agent/guest/Caddyfile /etc/caddy/Caddyfile
   sudo systemctl reload caddy
   ```

7. Verify the gates locally **before exposing the ingress**. Include
   `Host: hermes.apps.fondevilla.io` when probing Caddy; for direct loopback
   dashboard calls include the same host so the intended public origin is used.
   `/api/status` should advertise `auth_required: true` and a configured provider;
   `/api/config` must reject anonymous access. API `/v1/models` must reject a
   missing/wrong bearer and succeed with the real key loaded privately.
8. Merge/sync the Ingress, verify DNS/TLS, then run the checks below. Verify
   login, a real Chat WebSocket and one deliberate harmless authenticated API
   completion separately. Successful model listing alone does not prove inference.

### Validation

```sh
# Local fixture-based routing regression; does not test Hermes authentication:
python3 k8s/apps/workloads/hermes-agent/guest/test_routes.py
caddy validate --config k8s/apps/workloads/hermes-agent/guest/Caddyfile --adapter caddyfile
systemd-analyze --user verify k8s/apps/workloads/hermes-agent/guest/hermes-web.service
kustomize build k8s/apps/workloads/hermes-agent/overlays/management
# Requires authenticated cluster access:
kubectl --context homelab apply --dry-run=server -k k8s/apps/workloads/hermes-agent/overlays/management
kubectl --context homelab -n kubevirt get ingress hermes-agent
kubectl --context homelab -n kubevirt get certificate hermes-agent-tls
```

After deployment, `/api/config` must reject anonymous dashboard requests and
`/openai/v1/models` must return 401 without an API bearer key. Test authenticated
calls with secrets read privately into an HTTP client, not printed into logs.
`/openai/health` is a public liveness probe, not an authentication test. Confirm
`/inmobiliaria/` remains available and the old hostname still serves the project
index. Device/browser login, streaming, DNS/TLS and real inference are separate
acceptance checks; fixture tests do not establish them.

### Rollback

Remove the Ingress from the management overlay, sync, and explicitly delete it
if appropriate: this workload has automatic pruning disabled, so removing the
file alone may leave the old Ingress active. Preserve the VM and DataVolume.
Restore the backed-up Caddyfile, reload Caddy, disable/stop `hermes-web.service`,
and remove only the HTTP drop-in from the gateway before a planned restart.
Keep the private env file until credentials are deliberately revoked/rotated.

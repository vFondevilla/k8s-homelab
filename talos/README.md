# Talos Configs

## Secret management pattern

Secrets are extracted into a `secrets.yaml` bundle (via `talosctl gen secrets --from-controlplane-config`) and SOPS-encrypted. The full `controlplane.yaml`, `worker.yaml`, and `talosconfig` are gitignored — generated on demand.

Each cluster dir has:
```
<cluster>/
  secrets.yaml               # SOPS encrypted, commit this
  patches/
    controlplane.yaml        # non-secret machine/cluster config overrides, commit this
    network-extensions.yaml  # extra docs (LinkConfig, VLANConfig, etc.) to append, commit this
  controlplane.yaml          # gitignored, generated
  worker.yaml                # gitignored, generated
  talosconfig                # gitignored, generated
```

To regenerate configs after cloning or changing a patch:
```bash
task gen-<cluster-name>
```

The Taskfile task uses `sops exec-file secrets.yaml 'talosctl gen config ... --with-secrets {} ...'` — no manual decrypt/encrypt needed.

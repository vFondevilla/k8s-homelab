# ExternalDNS

ExternalDNS publishes DNS records for the management cluster. It also applies the static `DNSEndpoint` records in this component.

This component is a platform network component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates the ExternalDNS controller in the `external-dns` namespace. It creates static DNS records in the `default` namespace.

## Dependencies

The controller uses a Cloudflare API token from 1Password. External Secrets Operator creates the Kubernetes Secret.

The static records use the `DNSEndpoint` custom resource from the ExternalDNS chart.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/external-dns/overlays/management
```

## Migration constraint

Preserve the `in-cluster-external-dns` Application name during a source-path migration.

Preserve the Deployment, pod, and ExternalSecret identities when the rendered resources do not change.

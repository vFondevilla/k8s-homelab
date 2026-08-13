# Tinkerbell

Tinkerbell provides bare-metal provisioning services. This component is currently paused on the management cluster.

This component is a platform provisioning component.

## Overlay

The management overlay is `overlays/management/`.

The overlay creates resources in the `tinkerbell` namespace. It also creates cluster-wide storage, network, and permission resources.

## Dependencies

The deployment uses the Tinkerbell Helm chart at version `v0.22.1`.

The component uses the Cilium LoadBalancer address `10.253.0.50`. It connects to host interface `eno4.7`.

The hook service uses local storage at `/var/local/tinkerbell/hookos`.

## Render

Operate this command from the repository root:

```sh
kustomize build --enable-helm k8s/apps/platform/tinkerbell/overlays/management
```

## Migration constraint

Preserve the `in-cluster-tinkerbell` Application name.

Keep automated sync disabled. A source-path migration must not deploy the paused resources.

Do not synchronize this component until its network, storage, and security settings pass a separate review.

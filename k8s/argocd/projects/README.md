# Argo CD projects

This directory owns Argo CD `AppProject` resources only.

The `tenant` project permits the repository to deploy resources to registered tenant clusters.

The active Argo root does not include this directory. Activate the project with the protected tenant ApplicationSets.

Component manifests and tenant claims belong elsewhere in `k8s/`.

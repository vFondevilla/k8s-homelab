# Ephemeral tenant profile

This profile documents the bootstrap add-ons and labels for short-lived tenant
clusters. An ephemeral profile is not a second permanent cluster identity.

Every request must carry an owner, purpose, creation timestamp, expiry or
maximum lifetime, Kubernetes version, sizing, CIDRs, and selected profile.

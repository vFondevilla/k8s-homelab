# External Secrets Operator platform component

The management and tenant overlays use the singular `base/` layout. Tenant
secret-store configuration remains opt-in and must not select the management
cluster accidentally.

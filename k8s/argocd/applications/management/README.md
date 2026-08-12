# Management Applications

This directory owns Argo CD `Application` resources for the existing
management cluster. Application names, destinations, and sync policies must be
preserved during migration unless an explicit architecture decision changes
them.

Only applications with a renderable, verified source are included in the new
root. Storage and backup wrappers remain staged here but are excluded from the
active Kustomization until their legacy sources are normalized.

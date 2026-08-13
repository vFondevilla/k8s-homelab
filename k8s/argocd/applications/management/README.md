# Management Applications

This directory contains staged Argo CD `Application` resources for the management cluster.

The active Argo root does not include this directory. The management ApplicationSet owns active component Applications.

Use these wrappers only for components that are outside ApplicationSet discovery.

Before you activate a wrapper, compare its name, destination, source, and sync policy with the live inventory.

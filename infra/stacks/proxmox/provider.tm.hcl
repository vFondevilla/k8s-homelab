# All stacks below this directory use the same provider version.
generate_hcl "_terramate_provider.tf" {
  content {
    terraform {
      required_providers {
        proxmox = {
          source  = "bpg/proxmox"
          version = "0.122.0"
        }
      }
    }

    # Endpoint, API token, and TLS configuration come from PROXMOX_VE_*.
    provider "proxmox" {}
  }
}

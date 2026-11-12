resource "proxmox_virtual_environment_vm" "vm" {
  name      = var.vm.name
  node_name = var.vm.node_name
  vm_id     = var.vm.vm_id
  on_boot   = true

  clone {
    vm_id        = var.vm.template_id
    datastore_id = var.vm.datastore_id
    full         = true
  }

  cpu {
    cores = var.vm.cores
    type  = "host"
  }

  memory {
    dedicated = var.vm.memory_mb
  }

  agent {
    enabled = var.vm.guest_agent
  }

  network_device {
    bridge = var.vm.bridge
  }

  initialization {
    datastore_id = var.vm.datastore_id

    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }

    user_account {
      username = var.vm.username
      keys     = var.vm.ssh_public_keys
    }
  }
}

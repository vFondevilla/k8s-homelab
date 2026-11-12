variable "vm" {
  description = "A new VM cloned from a cloud-init template on the same Proxmox node."
  type = object({
    name            = string
    node_name       = string
    vm_id           = number
    template_id     = number
    datastore_id    = string
    ssh_public_keys = list(string)
    cores           = optional(number, 2)
    memory_mb       = optional(number, 2048)
    bridge          = optional(string, "vmbr0")
    username        = optional(string, "ubuntu")
    guest_agent     = optional(bool, false)
  })

  validation {
    condition     = var.vm.vm_id != var.vm.template_id
    error_message = "Use a new VM ID that differs from the template ID."
  }

  validation {
    condition     = length(var.vm.ssh_public_keys) > 0
    error_message = "Provide at least one SSH public key for the VM user."
  }
}

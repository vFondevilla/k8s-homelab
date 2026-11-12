# Adopted from the running CRS305 configuration on 2026-11-12.

resource "routeros_ip_address" "management" {
  address   = "10.1.0.254/24"
  comment   = "defconf"
  disabled  = false
  interface = routeros_interface_ethernet.ether1.name
  network   = "10.1.0.0"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_route" "default" {
  disabled      = false
  distance      = 1
  dst_address   = "0.0.0.0/0"
  gateway       = "10.1.0.1"
  routing_table = "main"
  scope         = 30
  target_scope  = 10

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_route" "homelab" {
  distance      = 1
  dst_address   = "10.1.1.0/24"
  gateway       = "10.1.0.1"
  routing_table = "main"
  scope         = 30
  target_scope  = 10

  lifecycle {
    prevent_destroy = true
  }
}

# Adopted from the running CRS305 configuration on 2026-11-12.

resource "routeros_interface_list" "WAN" {
  name = "WAN"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_list" "LAN" {
  name = "LAN"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_list" "MGMT" {
  name = "MGMT"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_list_member" "wan_ether1" {
  disabled  = false
  interface = routeros_interface_ethernet.ether1.name
  list      = routeros_interface_list.WAN.name

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_list_member" "lan_bridge" {
  disabled  = false
  interface = routeros_interface_bridge.bridge.name
  list      = routeros_interface_list.LAN.name

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_list_member" "mgmt_ether1" {
  disabled  = false
  interface = routeros_interface_ethernet.ether1.name
  list      = routeros_interface_list.MGMT.name

  lifecycle {
    prevent_destroy = true
  }
}

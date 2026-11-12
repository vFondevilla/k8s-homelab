# Adopted from the running CRS305 configuration on 2026-11-12.

resource "routeros_interface_bridge" "bridge" {
  admin_mac           = "F4:1E:57:23:FA:40"
  ageing_time         = "5m"
  arp                 = "enabled"
  arp_timeout         = "auto"
  auto_mac            = false
  comment             = "defconf"
  dhcp_snooping       = false
  disabled            = false
  fast_forward        = true
  forward_delay       = "15s"
  igmp_snooping       = false
  max_learned_entries = "auto"
  max_message_age     = "20s"
  mtu                 = "auto"
  mvrp                = false
  name                = "bridge"
  port_cost_mode      = "long"
  priority            = "0x8000"
  protocol_mode       = "rstp"
  transmit_hold_count = 6
  vlan_filtering      = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_bridge" "sfp" {
  ageing_time         = "5m"
  arp                 = "enabled"
  arp_timeout         = "auto"
  auto_mac            = true
  dhcp_snooping       = false
  disabled            = false
  fast_forward        = true
  forward_delay       = "15s"
  igmp_snooping       = false
  max_learned_entries = "auto"
  max_message_age     = "20s"
  mtu                 = "auto"
  mvrp                = false
  name                = "sfp"
  port_cost_mode      = "long"
  priority            = "0x8000"
  protocol_mode       = "rstp"
  transmit_hold_count = 6
  vlan_filtering      = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_bridge_port" "sfp_sfpplus1" {
  auto_isolate            = false
  bpdu_guard              = false
  bridge                  = routeros_interface_bridge.bridge.name
  broadcast_flood         = true
  comment                 = "defconf"
  disabled                = false
  edge                    = "auto"
  fast_leave              = false
  frame_types             = "admit-all"
  horizon                 = "none"
  hw                      = true
  ingress_filtering       = true
  interface               = routeros_interface_ethernet.sfp_sfpplus1.name
  learn                   = "auto"
  multicast_router        = "temporary-query"
  mvrp_applicant_state    = "normal-participant"
  mvrp_registrar_state    = "normal"
  point_to_point          = "auto"
  priority                = "0x80"
  pvid                    = 1
  restricted_role         = false
  restricted_tcn          = false
  tag_stacking            = false
  trusted                 = false
  unknown_multicast_flood = true
  unknown_unicast_flood   = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_bridge_port" "sfp_sfpplus2" {
  auto_isolate            = false
  bpdu_guard              = false
  bridge                  = routeros_interface_bridge.bridge.name
  broadcast_flood         = true
  comment                 = "defconf"
  disabled                = false
  edge                    = "auto"
  fast_leave              = false
  frame_types             = "admit-all"
  horizon                 = "none"
  hw                      = true
  ingress_filtering       = true
  interface               = routeros_interface_ethernet.sfp_sfpplus2.name
  learn                   = "auto"
  multicast_router        = "temporary-query"
  mvrp_applicant_state    = "normal-participant"
  mvrp_registrar_state    = "normal"
  point_to_point          = "auto"
  priority                = "0x80"
  pvid                    = 1
  restricted_role         = false
  restricted_tcn          = false
  tag_stacking            = false
  trusted                 = false
  unknown_multicast_flood = true
  unknown_unicast_flood   = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_bridge_port" "sfp_sfpplus3" {
  auto_isolate            = false
  bpdu_guard              = false
  bridge                  = routeros_interface_bridge.bridge.name
  broadcast_flood         = true
  comment                 = "defconf"
  disabled                = false
  edge                    = "auto"
  fast_leave              = false
  frame_types             = "admit-all"
  horizon                 = "none"
  hw                      = true
  ingress_filtering       = true
  interface               = routeros_interface_ethernet.sfp_sfpplus3.name
  learn                   = "auto"
  multicast_router        = "temporary-query"
  mvrp_applicant_state    = "normal-participant"
  mvrp_registrar_state    = "normal"
  point_to_point          = "auto"
  priority                = "0x80"
  pvid                    = 1
  restricted_role         = false
  restricted_tcn          = false
  tag_stacking            = false
  trusted                 = false
  unknown_multicast_flood = true
  unknown_unicast_flood   = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_bridge_port" "sfp_sfpplus4" {
  auto_isolate            = false
  bpdu_guard              = false
  bridge                  = routeros_interface_bridge.bridge.name
  broadcast_flood         = true
  comment                 = "defconf"
  disabled                = false
  edge                    = "auto"
  fast_leave              = false
  frame_types             = "admit-all"
  horizon                 = "none"
  hw                      = true
  ingress_filtering       = true
  interface               = routeros_interface_ethernet.sfp_sfpplus4.name
  learn                   = "auto"
  multicast_router        = "temporary-query"
  mvrp_applicant_state    = "normal-participant"
  mvrp_registrar_state    = "normal"
  point_to_point          = "auto"
  priority                = "0x80"
  pvid                    = 1
  restricted_role         = false
  restricted_tcn          = false
  tag_stacking            = false
  trusted                 = false
  unknown_multicast_flood = true
  unknown_unicast_flood   = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_bridge_vlan" "storage" {
  bridge   = routeros_interface_bridge.bridge.name
  disabled = false
  tagged   = [routeros_interface_bridge.bridge.name]
  vlan_ids = ["254"]

  lifecycle {
    prevent_destroy = true
  }
}

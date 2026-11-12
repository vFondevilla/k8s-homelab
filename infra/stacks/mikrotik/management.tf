# Adopted from the running CRS305 configuration on 2026-11-12.

resource "routeros_ip_neighbor_discovery_settings" "switch" {
  discover_interface_list  = routeros_interface_list.MGMT.name
  discover_interval        = "30s"
  lldp_dcbx                = true
  lldp_mac_phy_config      = false
  lldp_max_frame_size      = false
  lldp_med_net_policy_vlan = "disabled"
  lldp_vlan_info           = false
  mode                     = "tx-and-rx"
  protocol                 = ["cdp", "lldp", "mndp"]

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_snmp" "switch" {
  enabled         = true
  src_address     = "::"
  trap_community  = "public"
  trap_generators = "temp-exception"
  trap_version    = 1
  vrf             = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_system_clock" "switch" {
  time_zone_autodetect = true
  time_zone_name       = "Europe/Madrid"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_system_note" "switch" {
  note              = ""
  show_at_cli_login = false
  show_at_login     = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_system_identity" "switch" {
  name = "MikroTik"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_system_user" "admin" {
  comment            = "system default user"
  disabled           = false
  group              = "full"
  inactivity_policy  = "none"
  inactivity_timeout = "10m"
  name               = "admin"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_snmp_community" "public" {
  addresses               = ["::/0"]
  authentication_protocol = "MD5"
  disabled                = false
  encryption_protocol     = "DES"
  name                    = "public"
  read_access             = true
  security                = "none"
  write_access            = false

  lifecycle {
    prevent_destroy = true
  }
}

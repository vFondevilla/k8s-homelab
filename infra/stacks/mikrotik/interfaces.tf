# Adopted from the running CRS305 configuration on 2026-11-12.

resource "routeros_interface_ethernet" "ether1" {
  advertise                  = "10M-baseT-half,10M-baseT-full,100M-baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full"
  arp                        = "enabled"
  arp_timeout                = "auto"
  auto_negotiation           = true
  bandwidth                  = "unlimited/unlimited"
  disabled                   = false
  factory_name               = "ether1"
  l2mtu                      = 1592
  loop_protect               = "default"
  loop_protect_disable_time  = "5m"
  loop_protect_send_interval = "5s"
  mac_address                = "F4:1E:57:23:FA:3F"
  mtu                        = 1500
  name                       = "ether1"
  rx_flow_control            = "off"
  tx_flow_control            = "off"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_ethernet" "sfp_sfpplus1" {
  advertise                  = "10M-baseT-half,10M-baseT-full,100M-baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full,1G-baseX,2.5G-baseT,2.5G-baseX,5G-baseT,10G-baseT,10G-baseSR-LR,10G-baseCR"
  arp                        = "enabled"
  arp_timeout                = "auto"
  auto_negotiation           = true
  bandwidth                  = "unlimited/unlimited"
  disabled                   = false
  factory_name               = "sfp-sfpplus1"
  l2mtu                      = 9000
  loop_protect               = "default"
  loop_protect_disable_time  = "5m"
  loop_protect_send_interval = "5s"
  mac_address                = "F4:1E:57:23:FA:40"
  mtu                        = 9000
  name                       = "sfp-sfpplus1"
  rx_flow_control            = "off"
  sfp_ignore_rx_los          = false
  sfp_rate_select            = "high"
  sfp_shutdown_temperature   = 95
  tx_flow_control            = "off"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_ethernet" "sfp_sfpplus2" {
  advertise                  = "10M-baseT-half,10M-baseT-full,100M-baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full,1G-baseX,2.5G-baseT,2.5G-baseX,5G-baseT,10G-baseT,10G-baseSR-LR,10G-baseCR"
  arp                        = "enabled"
  arp_timeout                = "auto"
  auto_negotiation           = true
  bandwidth                  = "unlimited/unlimited"
  disabled                   = false
  factory_name               = "sfp-sfpplus2"
  l2mtu                      = 9000
  loop_protect               = "default"
  loop_protect_disable_time  = "5m"
  loop_protect_send_interval = "5s"
  mac_address                = "F4:1E:57:23:FA:41"
  mtu                        = 9000
  name                       = "sfp-sfpplus2"
  rx_flow_control            = "off"
  sfp_ignore_rx_los          = false
  sfp_rate_select            = "high"
  sfp_shutdown_temperature   = 95
  tx_flow_control            = "off"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_ethernet" "sfp_sfpplus3" {
  advertise                  = "10M-baseT-half,10M-baseT-full,100M-baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full,1G-baseX,2.5G-baseT,2.5G-baseX,5G-baseT,10G-baseT,10G-baseSR-LR,10G-baseCR"
  arp                        = "enabled"
  arp_timeout                = "auto"
  auto_negotiation           = true
  bandwidth                  = "unlimited/unlimited"
  disabled                   = false
  factory_name               = "sfp-sfpplus3"
  l2mtu                      = 9000
  loop_protect               = "default"
  loop_protect_disable_time  = "5m"
  loop_protect_send_interval = "5s"
  mac_address                = "F4:1E:57:23:FA:42"
  mtu                        = 9000
  name                       = "sfp-sfpplus3"
  rx_flow_control            = "off"
  sfp_ignore_rx_los          = false
  sfp_rate_select            = "high"
  sfp_shutdown_temperature   = 95
  tx_flow_control            = "off"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_ethernet" "sfp_sfpplus4" {
  advertise                  = "10M-baseT-half,10M-baseT-full,100M-baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full,1G-baseX,2.5G-baseT,2.5G-baseX,5G-baseT,10G-baseT,10G-baseSR-LR,10G-baseCR"
  arp                        = "enabled"
  arp_timeout                = "auto"
  auto_negotiation           = true
  bandwidth                  = "unlimited/unlimited"
  disabled                   = false
  factory_name               = "sfp-sfpplus4"
  l2mtu                      = 9000
  loop_protect               = "default"
  loop_protect_disable_time  = "5m"
  loop_protect_send_interval = "5s"
  mac_address                = "F4:1E:57:23:FA:43"
  mtu                        = 9000
  name                       = "sfp-sfpplus4"
  rx_flow_control            = "off"
  sfp_ignore_rx_los          = false
  sfp_rate_select            = "high"
  sfp_shutdown_temperature   = 95
  tx_flow_control            = "off"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_interface_vlan" "storageVlan" {
  arp                        = "enabled"
  arp_timeout                = "auto"
  comment                    = "storage vlan"
  disabled                   = true
  interface                  = routeros_interface_ethernet.sfp_sfpplus4.name
  loop_protect               = "default"
  loop_protect_disable_time  = "5m"
  loop_protect_send_interval = "5s"
  mtu                        = "8996"
  mvrp                       = false
  name                       = "storageVlan"
  use_service_tag            = false
  vlan_id                    = 254

  lifecycle {
    prevent_destroy = true
  }
}

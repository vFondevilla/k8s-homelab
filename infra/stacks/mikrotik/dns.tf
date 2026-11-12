# The DNS resource requires state adoption because provider 1.99.1 has no importer.
resource "routeros_ip_dns" "switch" {
  address_list_extra_time     = "0s"
  allow_remote_requests       = false
  cache_max_ttl               = "1w"
  cache_size                  = 2048
  doh_max_concurrent_queries  = 50
  doh_max_server_connections  = 5
  doh_timeout                 = "5s"
  max_concurrent_queries      = 100
  max_concurrent_tcp_sessions = 20
  max_udp_packet_size         = 4096
  mdns_repeat_ifaces          = []
  query_server_timeout        = "2s"
  query_total_timeout         = "10s"
  servers                     = ["10.1.0.1"]
  use_doh_server              = ""
  verify_doh_cert             = false
  vrf                         = "main"

  lifecycle {
    prevent_destroy = true
  }
}

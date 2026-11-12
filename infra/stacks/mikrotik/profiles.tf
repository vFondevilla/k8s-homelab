# Adopted from the running CRS305 configuration on 2026-11-12.

resource "routeros_ip_hotspot_profile" "default" {
  hotspot_address      = "0.0.0.0"
  html_directory       = "hotspot"
  http_cookie_lifetime = "3d"
  http_proxy           = "0.0.0.0:0"
  login_by             = ["cookie", "http-chap"]
  name                 = "default"
  smtp_server          = "0.0.0.0"
  split_user_domain    = false
  use_radius           = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_ipsec_profile" "default" {
  dh_group             = ["modp2048", "modp1024"]
  dpd_interval         = "2m"
  dpd_maximum_failures = 5
  enc_algorithm        = ["aes-128", "3des"]
  hash_algorithm       = "sha1"
  lifetime             = "1d"
  name                 = "default"
  nat_traversal        = true
  proposal_check       = "obey"

  lifecycle {
    prevent_destroy = true
  }
}

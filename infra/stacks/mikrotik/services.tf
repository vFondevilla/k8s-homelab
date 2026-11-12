# Adopted from the running CRS305 configuration on 2026-11-12.

resource "routeros_ip_service" "telnet" {
  disabled     = false
  max_sessions = 20
  numbers      = "telnet"
  port         = 23
  vrf          = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_service" "ftp" {
  disabled     = false
  max_sessions = 20
  numbers      = "ftp"
  port         = 21
  vrf          = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_service" "www" {
  disabled     = false
  max_sessions = 20
  numbers      = "www"
  port         = 80
  vrf          = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_service" "ssh" {
  disabled     = false
  max_sessions = 20
  numbers      = "ssh"
  port         = 22
  vrf          = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_service" "www_ssl" {
  certificate  = "none"
  disabled     = true
  max_sessions = 20
  numbers      = "www-ssl"
  port         = 443
  tls_version  = "any"
  vrf          = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_service" "api" {
  disabled     = false
  max_sessions = 20
  numbers      = "api"
  port         = 8728
  vrf          = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_service" "winbox" {
  disabled     = false
  max_sessions = 20
  numbers      = "winbox"
  port         = 8291
  vrf          = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_service" "api_ssl" {
  certificate  = "none"
  disabled     = false
  max_sessions = 20
  numbers      = "api-ssl"
  port         = 8729
  tls_version  = "any"
  vrf          = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "routeros_ip_ssh_server" "switch" {
  always_allow_password_login = false
  ciphers                     = "auto"
  forwarding_enabled          = "no"
  host_key_size               = 2048
  host_key_type               = "rsa"
  strong_crypto               = false

  lifecycle {
    prevent_destroy = true
  }
}

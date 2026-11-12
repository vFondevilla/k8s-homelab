provider "unifi" {
  # Authentication, site, and TLS options come from UNIFI_* environment variables.
  api_url = "https://10.1.0.1"
}

resource "unifi_bgp" "gateway" {
  enabled = true
  config  = file("${path.module}/bgp.conf")

  lifecycle {
    prevent_destroy = true
  }
}

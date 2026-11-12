# The native provider still models the pre-7.17 singleton OpenVPN server.
# Select writable fields so runtime flags do not enter the managed configuration.
locals {
  ovpn_server_path = "/interface/ovpn-server/server"
  ovpn_server_data = jsondecode(file("${path.module}/openvpn.json"))
}

resource "restapi_object" "ovpn_server" {
  path      = local.ovpn_server_path
  object_id = "*1"
  read_path = "${local.ovpn_server_path}/{id}?.proplist=${join(",", sort(keys(local.ovpn_server_data)))}"
  data      = jsonencode(local.ovpn_server_data)

  lifecycle {
    prevent_destroy = true
  }
}

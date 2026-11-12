terraform {
  required_providers {
    routeros = {
      source  = "terraform-routeros/routeros"
      version = "1.99.1"
    }
    restapi = {
      source  = "Mastercard/restapi"
      version = "3.0.0"
    }
  }
}

# The existing switch API and credentials come from ROS_* in .env.op.
provider "routeros" {}

# RouterOS 7.17 uses named OpenVPN servers, which the RouterOS provider does not model.
provider "restapi" {
  id_attribute         = ".id"
  create_method        = "PUT"
  update_method        = "PATCH"
  write_returns_object = true
}

terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    unifi = {
      source  = "ubiquiti-community/unifi"
      version = "0.65.0"
    }
  }

  backend "s3" {
    key          = "unifi/terraform.tfstate"
    region       = "auto"
    use_lockfile = true

    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}

# State keys are explicit so moving a stack does not change its remote state.
generate_hcl "_terramate_backend.tf" {
  content {
    terraform {
      required_version = ">= 1.10.0, < 2.0.0"

      backend "s3" {
        key          = global.state_key
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
  }
}

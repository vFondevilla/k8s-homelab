stack {
  id          = "84ad39f7-4976-47eb-8c66-71af1c01f2bb"
  name        = "unifi"
  description = "UniFi gateway BGP configuration"
  tags        = ["unifi", "network"]
  watch = [
    "/infra/.env.op",
    "/infra/mise.toml",
    "/infra/taskfiles/stack.yml",
    "/infra/scripts/with-env.sh",
    "/infra/scripts/backup_state.py",
  ]
}

globals {
  state_key = "unifi/terraform.tfstate"
}

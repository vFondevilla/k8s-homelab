stack {
  id          = "8ed66f6f-6e2b-4db0-ab23-57bea931b06c"
  name        = "mikrotik"
  description = "MikroTik CRS305 SFP switch configuration"
  tags        = ["mikrotik", "network"]
  watch = [
    "/infra/.env.op",
    "/infra/mise.toml",
    "/infra/taskfiles/stack.yml",
    "/infra/scripts/with-env.sh",
    "/infra/scripts/backup_state.py",
  ]
}

globals {
  state_key = "mikrotik/terraform.tfstate"
}

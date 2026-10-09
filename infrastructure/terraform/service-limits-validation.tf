resource "terraform_data" "service_limits" {
  lifecycle {
    precondition {
      condition     = length(local.access_groups) < 100000
      error_message = "Identity Center group count must remain below 100000."
    }
    precondition {
      condition     = length(local.permission_sets) < 2000
      error_message = "Identity Center permission set count must remain below 2000."
    }
    precondition {
      condition     = length(var.access_types) * length(var.duration_tiers) < 50
      error_message = "Provisioned permission sets per account must remain below 50."
    }
  }
}

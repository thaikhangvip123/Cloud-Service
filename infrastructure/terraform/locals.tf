locals {
  resource_prefix = "pa-${var.environment}"

  common_tags = {
    Application = "production-access-portal"
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  environment_config = {
    sit  = { pitr = false, retention = 7, rate = 10 }
    uat  = { pitr = true, retention = 14, rate = 10 }
    prod = { pitr = true, retention = 90, rate = 50 }
  }
  config = local.environment_config[var.environment]

  policy_arns = {
    ReadOnly  = "arn:aws:iam::aws:policy/ReadOnlyAccess"
    PowerUser = "arn:aws:iam::aws:policy/PowerUserAccess"
    Admin     = "arn:aws:iam::aws:policy/AdministratorAccess"
  }
  session_durations = {
    "1h"  = "PT1H"
    "2h"  = "PT2H"
    "4h"  = "PT4H"
    "8h"  = "PT8H"
    "12h" = "PT12H"
  }

  permission_sets = {
    for pair in setproduct(var.access_types, var.duration_tiers) :
    "${pair[0]}|${pair[1]}" => {
      access_type = pair[0]
      tier        = pair[1]
    }
  }
  access_groups = {
    for item in setproduct(keys(var.target_accounts), var.access_types, var.duration_tiers) :
    "${item[0]}|${item[1]}|${item[2]}" => {
      account_key  = item[0]
      account_name = var.target_accounts[item[0]].account_name
      access_type  = item[1]
      tier         = item[2]
    }
  }
}

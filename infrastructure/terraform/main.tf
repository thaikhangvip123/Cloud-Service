module "identity_center" {
  source = "./modules/identity-center"
}

module "permission_sets" {
  source = "./modules/identity-center-permission-sets"

  instance_arn      = module.identity_center.instance_arn
  permission_sets   = local.permission_sets
  policy_arns       = local.policy_arns
  session_durations = local.session_durations
}

module "access_groups" {
  source = "./modules/identity-center-access-groups"

  identity_store_id = module.identity_center.identity_store_id
  resource_prefix   = local.resource_prefix
  access_groups     = local.access_groups
}

module "group_assignments" {
  source = "./modules/identity-center-group-assignments"

  instance_arn        = module.identity_center.instance_arn
  access_groups       = local.access_groups
  group_ids           = module.access_groups.group_ids
  permission_set_arns = module.permission_sets.permission_set_arns
  target_accounts     = var.target_accounts
}

module "access_sessions" {
  source = "./modules/dynamodb"

  table_name = "${local.resource_prefix}-access-sessions-${var.aws_region}"
  pitr       = local.config.pitr
}

module "approval_tokens" {
  source = "./modules/dynamodb-approval-tokens"

  table_name = "${local.resource_prefix}-approval-tokens-${var.aws_region}"
  pitr       = local.config.pitr
}

module "secrets" {
  source = "./modules/secrets-manager"

  resource_prefix      = local.resource_prefix
  region               = var.aws_region
  jira_credentials     = jsonencode({ base_url = var.jira_base_url, email = var.jira_email, api_token = var.jira_api_token })
  webhook_auth         = jsonencode({ api_key = var.api_key_value, hmac_secret = var.webhook_hmac_secret })
  approval_token_value = jsonencode({ hmac_secret = var.approval_token_secret })
}

module "ses" {
  source = "./modules/ses"

  sender_email = var.ses_sender_email
}

module "lambdas" {
  source = "./modules/lambda-functions"

  resource_prefix             = local.resource_prefix
  region                      = var.aws_region
  identity_store_id           = module.identity_center.identity_store_id
  access_sessions_table       = module.access_sessions.table_name
  access_sessions_stream_arn  = module.access_sessions.stream_arn
  approval_tokens_table       = module.approval_tokens.table_name
  access_group_mapping_secret = module.secrets.access_group_mapping_secret_name
  jira_credentials_secret     = module.secrets.jira_credentials_secret_name
  webhook_auth_secret         = module.secrets.webhook_auth_secret_name
  token_secret_name           = module.secrets.token_secret_name
  secret_arns                 = module.secrets.secret_arns
  ses_sender_email            = var.ses_sender_email
  identity_center_portal_url  = var.identity_center_portal_url
  approval_base_url           = var.approval_base_url
  log_retention_days          = local.config.retention
  packages_dir                = "${path.root}/../packages"
}

module "api" {
  source = "./modules/api-gateway"

  resource_prefix         = local.resource_prefix
  region                  = var.aws_region
  executor_lambda_arn     = module.lambdas.executor_arn
  executor_lambda_name    = module.lambdas.executor_name
  email_lambda_arn        = module.lambdas.email_approval_arn
  email_lambda_name       = module.lambdas.email_approval_name
  api_key_value           = var.api_key_value
  rate_limit              = local.config.rate
  quota_limit             = 10000
  executor_invoke_arn     = module.lambdas.executor_invoke_arn
  email_lambda_invoke_arn = module.lambdas.email_approval_invoke_arn
}

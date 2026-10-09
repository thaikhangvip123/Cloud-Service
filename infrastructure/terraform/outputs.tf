output "deployment_summary" {
  value = {
    environment             = var.environment
    region                  = var.aws_region
    api_gateway_url         = module.api.invoke_url
    access_sessions_table   = module.access_sessions.table_name
    approval_tokens_table   = module.approval_tokens.table_name
    executor_lambda         = module.lambdas.executor_name
    expiry_lambda           = module.lambdas.expiry_name
    email_approval_lambda   = module.lambdas.email_approval_name
    access_group_count      = length(local.access_groups)
    permission_set_count    = length(local.permission_sets)
    ses_manual_verification = "Verify ${var.ses_sender_email} from the SES verification email."
  }
}

output "api_gateway_url" {
  value = module.api.invoke_url
}

output "provision_access_endpoint" {
  value = "${module.api.invoke_url}/provision-access"
}

output "email_approval_request_endpoint" {
  value = "${module.api.invoke_url}/email-approval/request"
}

output "email_approval_action_endpoint" {
  value = "${module.api.invoke_url}/email-approval/action"
}

output "access_sessions_table_name" {
  value = module.access_sessions.table_name
}

output "approval_tokens_table_name" {
  value = module.approval_tokens.table_name
}

output "executor_lambda_name" {
  value = module.lambdas.executor_name
}

output "expiry_lambda_name" {
  value = module.lambdas.expiry_name
}

output "email_approval_lambda_name" {
  value = module.lambdas.email_approval_name
}

output "identity_center_instance_arn" {
  value = module.identity_center.instance_arn
}

output "identity_store_id" {
  value = module.identity_center.identity_store_id
}

output "permission_set_arns" {
  value = module.permission_sets.permission_set_arns
}

output "access_group_ids" {
  value = module.access_groups.group_ids
}

output "access_groups" {
  value = module.access_groups.groups
}

output "target_accounts" {
  value = var.target_accounts
}

output "access_group_mapping_secret_name" {
  value = module.secrets.access_group_mapping_secret_name
}

output "jira_credentials_secret_name" {
  value = module.secrets.jira_credentials_secret_name
}

output "webhook_auth_secret_name" {
  value = module.secrets.webhook_auth_secret_name
}

output "token_secret_name" {
  value = module.secrets.token_secret_name
}

output "ses_sender_email" {
  value = var.ses_sender_email
}

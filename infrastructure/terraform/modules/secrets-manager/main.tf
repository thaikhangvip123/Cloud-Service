variable "resource_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "jira_credentials" {
  type      = string
  sensitive = true
}
variable "webhook_auth" {
  type      = string
  sensitive = true
}
variable "approval_token_value" {
  type      = string
  sensitive = true
}

locals {
  names = {
    jira    = "${var.resource_prefix}-jira-credentials-${var.region}"
    webhook = "${var.resource_prefix}-webhook-auth-${var.region}"
    mapping = "${var.resource_prefix}-access-group-mapping-${var.region}"
    token   = "${var.resource_prefix}-token-secret-${var.region}"
  }
}

resource "aws_secretsmanager_secret" "this" {
  for_each = local.names
  name     = each.value
}

resource "aws_secretsmanager_secret_version" "jira" {
  secret_id     = aws_secretsmanager_secret.this["jira"].id
  secret_string = var.jira_credentials
}

resource "aws_secretsmanager_secret_version" "webhook" {
  secret_id     = aws_secretsmanager_secret.this["webhook"].id
  secret_string = var.webhook_auth
}

resource "aws_secretsmanager_secret_version" "mapping" {
  secret_id     = aws_secretsmanager_secret.this["mapping"].id
  secret_string = jsonencode({ access_groups = {} })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret_version" "token" {
  secret_id     = aws_secretsmanager_secret.this["token"].id
  secret_string = var.approval_token_value
}

output "jira_credentials_secret_name" {
  value = aws_secretsmanager_secret.this["jira"].name
}

output "webhook_auth_secret_name" {
  value = aws_secretsmanager_secret.this["webhook"].name
}

output "access_group_mapping_secret_name" {
  value = aws_secretsmanager_secret.this["mapping"].name
}

output "token_secret_name" {
  value = aws_secretsmanager_secret.this["token"].name
}

output "secret_arns" {
  value = { for key, item in aws_secretsmanager_secret.this : key => item.arn }
}

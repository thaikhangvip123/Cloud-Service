variable "resource_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "executor_lambda_arn" {
  type = string
}

variable "executor_lambda_name" {
  type = string
}

variable "executor_invoke_arn" {
  type = string
}

variable "email_lambda_arn" {
  type = string
}

variable "email_lambda_name" {
  type = string
}

variable "email_lambda_invoke_arn" {
  type = string
}

variable "api_key_value" {
  type      = string
  sensitive = true
}

variable "rate_limit" {
  type = number
}

variable "quota_limit" {
  type = number
}

resource "aws_api_gateway_rest_api" "this" {
  name = "${var.resource_prefix}-api-${var.region}"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "provision" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "provision-access"
}

resource "aws_api_gateway_resource" "email" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "email-approval"
}

resource "aws_api_gateway_resource" "email_request" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_resource.email.id
  path_part   = "request"
}

resource "aws_api_gateway_resource" "email_action" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_resource.email.id
  path_part   = "action"
}

locals {
  routes = {
    provision = {
      resource_id = aws_api_gateway_resource.provision.id
      method      = "POST"
      api_key     = true
      invoke_arn  = var.executor_invoke_arn
    }
    email_request = {
      resource_id = aws_api_gateway_resource.email_request.id
      method      = "POST"
      api_key     = true
      invoke_arn  = var.email_lambda_invoke_arn
    }
    email_action = {
      resource_id = aws_api_gateway_resource.email_action.id
      method      = "GET"
      api_key     = false
      invoke_arn  = var.email_lambda_invoke_arn
    }
  }
}

resource "aws_api_gateway_method" "route" {
  for_each = local.routes

  rest_api_id      = aws_api_gateway_rest_api.this.id
  resource_id      = each.value.resource_id
  http_method      = each.value.method
  authorization    = "NONE"
  api_key_required = each.value.api_key
}

resource "aws_api_gateway_integration" "route" {
  for_each = local.routes

  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.route[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = each.value.invoke_arn
}

resource "aws_lambda_permission" "executor" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.executor_lambda_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.this.execution_arn}/*/POST/provision-access"
}

resource "aws_lambda_permission" "email" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.email_lambda_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.this.execution_arn}/*/*/email-approval/*"
}

resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.provision.id,
      aws_api_gateway_resource.email_request.id,
      aws_api_gateway_resource.email_action.id,
      values(aws_api_gateway_method.route)[*].id,
      values(aws_api_gateway_integration.route)[*].id,
    ]))
  }
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "this" {
  deployment_id = aws_api_gateway_deployment.this.id
  rest_api_id   = aws_api_gateway_rest_api.this.id
  stage_name    = replace(var.resource_prefix, "pa-", "")
}

resource "aws_api_gateway_api_key" "this" {
  name    = "${var.resource_prefix}-jira-api-key"
  value   = var.api_key_value
  enabled = true
}

resource "aws_api_gateway_usage_plan" "this" {
  name = "${var.resource_prefix}-usage-plan"
  api_stages {
    api_id = aws_api_gateway_rest_api.this.id
    stage  = aws_api_gateway_stage.this.stage_name
  }
  quota_settings {
    limit  = var.quota_limit
    period = "DAY"
  }
  throttle_settings {
    burst_limit = var.rate_limit * 2
    rate_limit  = var.rate_limit
  }
}

resource "aws_api_gateway_usage_plan_key" "this" {
  key_id        = aws_api_gateway_api_key.this.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.this.id
}

output "invoke_url" {
  value = aws_api_gateway_stage.this.invoke_url
}

output "api_name" {
  value = aws_api_gateway_rest_api.this.name
}

output "stage_name" {
  value = aws_api_gateway_stage.this.stage_name
}

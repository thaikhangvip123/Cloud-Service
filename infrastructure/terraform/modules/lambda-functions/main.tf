variable "resource_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "identity_store_id" {
  type = string
}

variable "access_sessions_table" {
  type = string
}

variable "access_sessions_stream_arn" {
  type = string
}

variable "approval_tokens_table" {
  type = string
}

variable "access_group_mapping_secret" {
  type = string
}

variable "jira_credentials_secret" {
  type = string
}

variable "webhook_auth_secret" {
  type = string
}

variable "token_secret_name" {
  type = string
}

variable "secret_arns" {
  type = map(string)
}

variable "ses_sender_email" {
  type = string
}

variable "identity_center_portal_url" {
  type = string
}

variable "approval_base_url" {
  type = string
}

variable "log_retention_days" {
  type = number
}

variable "packages_dir" {
  type = string
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  functions = {
    executor = {
      handler = "lambda_functions.executor.handler.lambda_handler"
      package = "${var.packages_dir}/executor.zip"
    }
    expiry = {
      handler = "lambda_functions.expiry.handler.lambda_handler"
      package = "${var.packages_dir}/expiry.zip"
    }
    email_approval = {
      handler = "lambda_functions.email_approval.handler.lambda_handler"
      package = "${var.packages_dir}/email_approval.zip"
    }
  }
  sessions_arn     = "arn:${data.aws_partition.current.partition}:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/${var.access_sessions_table}"
  tokens_arn       = "arn:${data.aws_partition.current.partition}:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/${var.approval_tokens_table}"
  ses_identity_arn = "arn:${data.aws_partition.current.partition}:ses:${var.region}:${data.aws_caller_identity.current.account_id}:identity/${var.ses_sender_email}"
}

resource "aws_iam_role" "lambda" {
  for_each = local.functions
  name     = "${var.resource_prefix}-${replace(each.key, "_", "-")}-role-${var.region}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "logs" {
  for_each   = local.functions
  role       = aws_iam_role.lambda[each.key].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "executor" {
  name = "jit-executor"
  role = aws_iam_role.lambda["executor"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          var.secret_arns["jira"],
          var.secret_arns["webhook"],
          var.secret_arns["mapping"]
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = local.sessions_arn
      },
      {
        Effect = "Allow"
        Action = [
          "identitystore:CreateGroupMembership",
          "identitystore:DeleteGroupMembership",
          "identitystore:DescribeGroup",
          "identitystore:ListUsers",
          "identitystore:DescribeUser",
          "identitystore:ListGroupMembershipsForMember"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = local.ses_identity_arn
        Condition = {
          StringEquals = { "ses:FromAddress" = var.ses_sender_email }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "expiry" {
  name = "jit-expiry"
  role = aws_iam_role.lambda["expiry"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.secret_arns["jira"]]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeStream",
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator"
        ]
        Resource = var.access_sessions_stream_arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:ListStreams"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = local.sessions_arn
      },
      {
        Effect   = "Allow"
        Action   = ["identitystore:DeleteGroupMembership"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = local.ses_identity_arn
        Condition = {
          StringEquals = { "ses:FromAddress" = var.ses_sender_email }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "email" {
  name = "jit-email-approval"
  role = aws_iam_role.lambda["email_approval"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          var.secret_arns["jira"],
          var.secret_arns["webhook"],
          var.secret_arns["token"]
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = local.tokens_arn
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = local.ses_identity_arn
        Condition = {
          StringEquals = { "ses:FromAddress" = var.ses_sender_email }
        }
      }
    ]
  })
}

resource "aws_lambda_layer_version" "dependencies" {
  filename            = "${var.packages_dir}/dependencies-layer.zip"
  layer_name          = "${var.resource_prefix}-dependencies-layer-${var.region}"
  compatible_runtimes = ["python3.12"]
  source_code_hash    = filebase64sha256("${var.packages_dir}/dependencies-layer.zip")
}

resource "aws_lambda_function" "this" {
  for_each = local.functions

  function_name    = "${var.resource_prefix}-${replace(each.key, "_", "-")}-${var.region}"
  role             = aws_iam_role.lambda[each.key].arn
  runtime          = "python3.12"
  handler          = each.value.handler
  filename         = each.value.package
  source_code_hash = filebase64sha256(each.value.package)
  timeout          = 30
  memory_size      = 256
  layers           = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      IDENTITY_STORE_ID           = var.identity_store_id
      ACCESS_SESSIONS_TABLE       = var.access_sessions_table
      APPROVAL_TOKENS_TABLE       = var.approval_tokens_table
      ACCESS_GROUP_MAPPING_SECRET = var.access_group_mapping_secret
      JIRA_CREDENTIALS_SECRET     = var.jira_credentials_secret
      WEBHOOK_AUTH_SECRET         = var.webhook_auth_secret
      TOKEN_SECRET_NAME           = var.token_secret_name
      SES_SENDER_EMAIL            = var.ses_sender_email
      IDENTITY_CENTER_PORTAL_URL  = var.identity_center_portal_url
      APPROVAL_BASE_URL           = var.approval_base_url
      ACCESS_GROUP_PREFIX         = "${var.resource_prefix}-"
      REQUIRE_HMAC                = "true"
    }
  }
}

resource "aws_cloudwatch_log_group" "this" {
  for_each = local.functions

  name              = "/aws/lambda/${aws_lambda_function.this[each.key].function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_event_source_mapping" "expiry" {
  event_source_arn               = var.access_sessions_stream_arn
  function_name                  = aws_lambda_function.this["expiry"].arn
  starting_position              = "LATEST"
  batch_size                     = 10
  maximum_retry_attempts         = 3
  bisect_batch_on_function_error = true
}

output "executor_name" {
  value = aws_lambda_function.this["executor"].function_name
}

output "executor_arn" {
  value = aws_lambda_function.this["executor"].arn
}

output "executor_invoke_arn" {
  value = aws_lambda_function.this["executor"].invoke_arn
}

output "expiry_name" {
  value = aws_lambda_function.this["expiry"].function_name
}

output "email_approval_name" {
  value = aws_lambda_function.this["email_approval"].function_name
}

output "email_approval_arn" {
  value = aws_lambda_function.this["email_approval"].arn
}

output "email_approval_invoke_arn" {
  value = aws_lambda_function.this["email_approval"].invoke_arn
}

output "email_approval_log_group" {
  value = aws_cloudwatch_log_group.this["email_approval"].name
}

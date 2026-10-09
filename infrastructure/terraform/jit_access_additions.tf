resource "aws_sns_topic" "alerts" {
  name = "${local.resource_prefix}-alerts-${var.aws_region}"
}

resource "aws_sns_topic_subscription" "admin_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.admin_email
}

resource "aws_cloudwatch_metric_alarm" "lambda_error_rate" {
  for_each = {
    executor       = module.lambdas.executor_name
    expiry         = module.lambdas.expiry_name
    email_approval = module.lambdas.email_approval_name
  }

  alarm_name          = "${local.resource_prefix}-${each.key}-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 5
  alarm_actions       = [aws_sns_topic.alerts.arn]

  metric_query {
    id          = "rate"
    expression  = "IF(invocations > 0, 100 * errors / invocations, 0)"
    label       = "Lambda error rate"
    return_data = true
  }
  metric_query {
    id = "errors"
    metric {
      namespace   = "AWS/Lambda"
      metric_name = "Errors"
      period      = 300
      stat        = "Sum"
      dimensions  = { FunctionName = each.value }
    }
  }
  metric_query {
    id = "invocations"
    metric {
      namespace   = "AWS/Lambda"
      metric_name = "Invocations"
      period      = 300
      stat        = "Sum"
      dimensions  = { FunctionName = each.value }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  for_each = {
    executor       = module.lambdas.executor_name
    expiry         = module.lambdas.expiry_name
    email_approval = module.lambdas.email_approval_name
  }

  alarm_name          = "${local.resource_prefix}-${each.key}-duration"
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 25000
  comparison_operator = "GreaterThanThreshold"
  dimensions          = { FunctionName = each.value }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_4xx_rate" {
  alarm_name          = "${local.resource_prefix}-api-4xx-rate"
  namespace           = "AWS/ApiGateway"
  metric_name         = "4XXError"
  statistic           = "Average"
  period              = 900
  evaluation_periods  = 1
  threshold           = 0.20
  comparison_operator = "GreaterThanThreshold"
  dimensions          = { ApiName = module.api.api_name, Stage = module.api.stage_name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_5xx_rate" {
  alarm_name          = "${local.resource_prefix}-api-5xx-rate"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5XXError"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0.01
  comparison_operator = "GreaterThanThreshold"
  dimensions          = { ApiName = module.api.api_name, Stage = module.api.stage_name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_throttles" {
  alarm_name          = "${local.resource_prefix}-dynamodb-throttles"
  namespace           = "AWS/DynamoDB"
  metric_name         = "ThrottledRequests"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  dimensions          = { TableName = module.access_sessions.table_name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ses_bounce_rate" {
  alarm_name          = "${local.resource_prefix}-ses-bounce-rate"
  namespace           = "AWS/SES"
  metric_name         = "Reputation.BounceRate"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0.05
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ses_complaint_rate" {
  alarm_name          = "${local.resource_prefix}-ses-complaint-rate"
  namespace           = "AWS/SES"
  metric_name         = "Reputation.ComplaintRate"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0.001
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_log_metric_filter" "failed_token_validation" {
  name           = "${local.resource_prefix}-failed-token-validation"
  log_group_name = module.lambdas.email_approval_log_group
  pattern        = "\"TOKEN_VALIDATION_FAILED\""

  metric_transformation {
    name      = "FailedTokenValidations"
    namespace = "ProductionAccessPortal"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "failed_token_validation" {
  alarm_name          = "${local.resource_prefix}-failed-token-validation"
  namespace           = "ProductionAccessPortal"
  metric_name         = "FailedTokenValidations"
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

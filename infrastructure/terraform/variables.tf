variable "environment" {
  type = string
  validation {
    condition     = contains(["sit", "uat", "prod"], var.environment)
    error_message = "environment must be sit, uat, or prod."
  }
}

variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be a valid AWS region name."
  }
}

variable "target_accounts" {
  type = map(object({
    account_id   = string
    account_name = string
  }))
  validation {
    condition     = alltrue([for account in values(var.target_accounts) : can(regex("^[0-9]{12}$", account.account_id))])
    error_message = "Every account_id must contain exactly 12 digits."
  }
  validation {
    condition = (
      length(var.target_accounts) > 0
      && alltrue([
        for account in values(var.target_accounts) :
        can(regex("^[A-Za-z0-9][A-Za-z0-9_-]*$", account.account_name))
      ])
      && length(distinct([
        for account in values(var.target_accounts) : account.account_name
      ])) == length(var.target_accounts)
    )
    error_message = "account_name values must be non-empty, safe, and unique."
  }
}

variable "access_types" {
  type    = list(string)
  default = ["ReadOnly", "PowerUser", "Admin"]
  validation {
    condition = (
      length(var.access_types) > 0
      && length(distinct(var.access_types)) == length(var.access_types)
      && alltrue([
        for item in var.access_types :
        contains(["ReadOnly", "PowerUser", "Admin"], item)
      ])
    )
    error_message = "access_types may only contain ReadOnly, PowerUser, and Admin."
  }
}

variable "duration_tiers" {
  type = list(string)
  validation {
    condition = (
      length(var.duration_tiers) > 0
      && length(distinct(var.duration_tiers)) == length(var.duration_tiers)
      && alltrue([
        for tier in var.duration_tiers :
        contains(["1h", "2h", "4h", "8h", "12h"], tier)
      ])
    )
    error_message = "duration_tiers contains an unsupported tier."
  }
}

variable "admin_email" {
  type = string
  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.admin_email))
    error_message = "admin_email must be a valid email address."
  }
}

variable "ses_sender_email" {
  type = string
  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.ses_sender_email))
    error_message = "ses_sender_email must be a valid email address."
  }
}

variable "identity_center_portal_url" {
  type = string
  validation {
    condition     = can(regex("^https://", var.identity_center_portal_url))
    error_message = "identity_center_portal_url must use HTTPS."
  }
}

variable "approval_base_url" {
  description = "Public GET /email-approval/action URL. Set after API creation or use a custom domain."
  type        = string
  validation {
    condition     = can(regex("^https://", var.approval_base_url))
    error_message = "approval_base_url must use HTTPS."
  }
}

variable "jira_base_url" {
  type      = string
  sensitive = true
  validation {
    condition     = can(regex("^https://", var.jira_base_url))
    error_message = "jira_base_url must use HTTPS."
  }
}

variable "jira_email" {
  type      = string
  sensitive = true
  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.jira_email))
    error_message = "jira_email must be a valid email address."
  }
}

variable "jira_api_token" {
  type      = string
  sensitive = true
  validation {
    condition     = length(var.jira_api_token) >= 16
    error_message = "jira_api_token must be at least 16 characters."
  }
}

variable "api_key_value" {
  type      = string
  sensitive = true
  validation {
    condition     = length(var.api_key_value) >= 20 && length(var.api_key_value) <= 128
    error_message = "api_key_value must contain 20 to 128 characters."
  }
}

variable "webhook_hmac_secret" {
  type      = string
  sensitive = true
  validation {
    condition     = length(var.webhook_hmac_secret) >= 32
    error_message = "webhook_hmac_secret must be at least 32 characters."
  }
}

variable "approval_token_secret" {
  type      = string
  sensitive = true
  validation {
    condition     = length(var.approval_token_secret) >= 32
    error_message = "approval_token_secret must be at least 32 characters."
  }
}

variable "enable_organization_trail" {
  description = "Capture management events across AWS Organizations target accounts."
  type        = bool
  default     = false
}

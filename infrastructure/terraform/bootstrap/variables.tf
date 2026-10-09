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
}

variable "state_bucket_name" {
  description = "Optional globally unique override for the Terraform state bucket."
  type        = string
  default     = null
}

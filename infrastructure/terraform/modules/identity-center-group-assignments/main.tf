variable "instance_arn" {
  type = string
}

variable "access_groups" {
  type = map(object({
    account_key  = string
    account_name = string
    access_type  = string
    tier         = string
  }))
}

variable "group_ids" {
  type = map(string)
}

variable "permission_set_arns" {
  type = map(string)
}

variable "target_accounts" {
  type = map(object({
    account_id   = string
    account_name = string
  }))
}

resource "aws_ssoadmin_account_assignment" "this" {
  for_each = var.access_groups

  instance_arn       = var.instance_arn
  permission_set_arn = var.permission_set_arns["${each.value.access_type}|${each.value.tier}"]
  principal_id       = var.group_ids[each.key]
  principal_type     = "GROUP"
  target_id          = var.target_accounts[each.value.account_key].account_id
  target_type        = "AWS_ACCOUNT"
}

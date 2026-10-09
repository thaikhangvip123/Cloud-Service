variable "identity_store_id" {
  type = string
}

variable "resource_prefix" {
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

resource "aws_identitystore_group" "this" {
  for_each = var.access_groups

  identity_store_id = var.identity_store_id
  display_name      = "${var.resource_prefix}-${each.value.account_name}-${each.value.access_type}-${each.value.tier}"
  description       = "JIT access group for ${each.value.account_name} ${each.value.access_type} ${each.value.tier}"
}

output "group_ids" {
  value = { for key, item in aws_identitystore_group.this : key => item.group_id }
}

output "groups" {
  value = {
    for key, item in aws_identitystore_group.this : key => {
      group_id     = item.group_id
      group_name   = item.display_name
      account_name = var.access_groups[key].account_name
    }
  }
}

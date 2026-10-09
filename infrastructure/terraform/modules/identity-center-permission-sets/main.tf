variable "instance_arn" {
  type = string
}

variable "permission_sets" {
  type = map(object({
    access_type = string
    tier        = string
  }))
}

variable "policy_arns" {
  type = map(string)
}

variable "session_durations" {
  type = map(string)
}

resource "aws_ssoadmin_permission_set" "this" {
  for_each = var.permission_sets

  instance_arn     = var.instance_arn
  name             = "${each.value.access_type}-${each.value.tier}"
  description      = "JIT ${each.value.access_type} access for ${each.value.tier}"
  session_duration = var.session_durations[each.value.tier]
}

resource "aws_ssoadmin_managed_policy_attachment" "this" {
  for_each = var.permission_sets

  instance_arn       = var.instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.this[each.key].arn
  managed_policy_arn = var.policy_arns[each.value.access_type]
}

output "permission_set_arns" {
  value      = { for key, item in aws_ssoadmin_permission_set.this : key => item.arn }
  depends_on = [aws_ssoadmin_managed_policy_attachment.this]
}

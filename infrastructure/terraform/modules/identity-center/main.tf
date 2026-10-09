data "aws_ssoadmin_instances" "current" {}

output "instance_arn" {
  value = tolist(data.aws_ssoadmin_instances.current.arns)[0]
}

output "identity_store_id" {
  value = tolist(data.aws_ssoadmin_instances.current.identity_store_ids)[0]
}

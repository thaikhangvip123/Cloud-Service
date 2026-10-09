output "state_bucket_name" {
  value = aws_s3_bucket.terraform_state.id
}

output "lock_table_name" {
  value = aws_dynamodb_table.terraform_lock.name
}

output "backend_hcl" {
  value = <<-EOT
    bucket         = "${aws_s3_bucket.terraform_state.id}"
    key            = "production-access-portal/${var.environment}/terraform.tfstate"
    region         = "${var.aws_region}"
    dynamodb_table = "${aws_dynamodb_table.terraform_lock.name}"
    encrypt        = true
  EOT
}

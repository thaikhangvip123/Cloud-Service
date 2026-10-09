variable "table_name" {
  type = string
}

variable "pitr" {
  type = bool
}

resource "aws_dynamodb_table" "this" {
  name             = var.table_name
  billing_mode     = "PAY_PER_REQUEST"
  hash_key         = "sessionId"
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  attribute {
    name = "sessionId"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.pitr
  }

  server_side_encryption {
    enabled = true
  }
}

output "table_name" {
  value = aws_dynamodb_table.this.name
}

output "table_arn" {
  value = aws_dynamodb_table.this.arn
}

output "stream_arn" {
  value = aws_dynamodb_table.this.stream_arn
}

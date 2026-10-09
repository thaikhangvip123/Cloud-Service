variable "sender_email" {
  type = string
}

resource "aws_ses_email_identity" "sender" {
  email = var.sender_email
}

output "sender_email" {
  value = aws_ses_email_identity.sender.email
}

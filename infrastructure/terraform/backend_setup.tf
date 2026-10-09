# Create the S3 backend and lock table in a separate bootstrap stack before
# enabling the backend block below. Backend files in backend/*.hcl provide
# environment-specific bucket/key/region settings.
terraform {
  backend "s3" {}
}

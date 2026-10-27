# Changelog

This file records agent-assisted system changes so later work can distinguish completed changes
from planned work. Secret values, real account IDs, and personal email addresses must never be
recorded here.

## 2026-10-27

### Changed

- Clarified the Lambda IAM rules in `AGENTS.md` to distinguish unscoped wildcard resources from
  resource-type-scoped ARN patterns used for runtime-created Identity Store resources.
- Documented a temporary SIT-only exception for `dynamodb:ListStreams`, which AWS does not support
  with resource-level permissions or service-specific condition keys.
- Required the `dynamodb:ListStreams` exception to remain isolated in a single-action statement and
  prohibited carrying it into UAT or PROD.
- Scoped Executor and Expiry Identity Store permissions to the current Identity Store, Terraform-
  managed access groups, and runtime-created user or membership resource types.
- Allowed read-only `DescribeGroup` across Identity Store group resources because emergency revoke
  must inspect dynamically discovered memberships before selecting project-managed groups; write
  actions remain scoped to Terraform-managed group ARNs.
- Made the unscoped `dynamodb:ListStreams` statement conditional on SIT and added a Terraform
  precondition that blocks the DynamoDB Streams expiry architecture in UAT and PROD.
- Added regression tests that detect additional unscoped Lambda IAM resources or removal of the
  SIT-only deployment guard.

### Scope and risk

- Terraform IAM policy generation changes for the Executor and Expiry Lambda roles.
- SIT keeps the existing DynamoDB Streams architecture and its required `ListStreams` permission.
- UAT and PROD plans are intentionally blocked until the precise scheduler design replaces the
  DynamoDB TTL/Streams expiry path.
- No AWS resource, secret, Terraform state, or live IAM role was changed by this local edit.

### Verification

- `git diff --check` passed.
- An independent subagent review found one wording ambiguity in the exception; it was corrected to
  state that only `dynamodb:ListStreams` may use `Resource = "*"` in the SIT Lambda Expiry role.
- A second independent review found a potential emergency-revoke regression when describing an
  unrelated group and a whitespace-sensitive regression test; both issues were corrected.
- `terraform fmt -recursive infrastructure/terraform` completed successfully.
- `terraform validate` passed for `infrastructure/terraform`.
- `git diff --check` passed, and a static search confirmed that the only remaining unscoped
  resource is the SIT-conditional `dynamodb:ListStreams` statement.
- The new IAM regression test compiled and all three test functions passed directly under the
  bundled Python 3.12 runtime.
- `black`, `pytest`, `flake8`, and `mypy` were not available in the local Python runtimes; CI must
  run the complete Python quality gates. The existing `.venv` still points to a removed Python 3.11
  installation.

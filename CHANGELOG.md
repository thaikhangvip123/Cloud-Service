# Changelog

This file records agent-assisted system changes so later work can distinguish completed changes
from planned work. Secret values, real account IDs, and personal email addresses must never be
recorded here.

## 2026-10-31

### Changed

- Synchronized the reproducible SIT GitHub OIDC policy templates with the Scheduler and API
  Gateway logging resources that were added to Terraform. The deployment roles remain scoped to
  the named SIT roles, schedule group, API Gateway account endpoint, and application log groups.
- Added encrypted apply-failure diagnostics to the Terraform deployment workflow. Raw apply logs
  remain hidden, are uploaded only after AES-256 encryption, and are retained for one day.
- Updated the ignored human-facing architecture documentation to describe Scheduler as the primary
  expiry trigger, DynamoDB TTL as delayed cleanup/SIT fallback, and the remaining active-credential
  revocation limitation.

### Verification

- Rendered all six SIT OIDC policies with placeholder identifiers; every policy parsed and remained
  below the 6,144-character managed-policy limit. The largest policy was 5,581 characters.
- Verified the Scheduler group and API Gateway `iam:PassRole` constraints with direct renderer
  assertions.
- Python source and tests compiled successfully with Python 3.12.14.
- Full Python quality gates could not be rerun locally because the existing `.venv` references a
  removed Python 3.11 installation and PyPI downloads were reset by the network. PR CI must run the
  pinned Python 3.12 toolchain.

## 2026-10-29

### Changed

- Required DynamoDB expiry events to identify the TTL service explicitly; records without the
  service principal are now ignored instead of being treated as TTL deletions.
- Made repeated grant webhooks reuse the matching active membership session without extending its
  expiry, and made Jira status transitions idempotent.
- Failed closed when an Identity Center email lookup is ambiguous or an existing membership has no
  matching active session.
- Stopped marking legacy direct-assignment sessions as expired when no safe legacy revocation path
  is configured; the expiry invocation now fails and alarms instead.
- Made partial emergency revocation failures escape the Lambda invocation so the error-rate alarm
  can fire.
- Corrected the API Gateway 4xx and 5xx alarms to calculate percentages from error and request
  counts instead of treating the raw metric average as an error rate.
- Added one-time EventBridge Scheduler expiry for all environments. Grant now rolls back the
  membership if schedule creation fails, and sessions remain available for 24 hours after expiry
  so Scheduler retries cannot race DynamoDB TTL cleanup. The DynamoDB stream consumer remains a
  SIT-only fallback.
- Added the legacy direct-assignment deletion path through SSO Admin, including status polling and
  fail-closed validation of legacy session fields.
- Added API Gateway access and execution logging without request bodies or headers, plus the
  account-level CloudWatch logging role required by API Gateway.
- Required timestamped HMAC validation on the email approval request webhook.
- Prefixed permission-set names with `pa-{environment}` to match the system naming convention.
- Added negative coverage for TTL identity checks, retry exhaustion, legacy sessions, webhook
  replays, ambiguous users, SES notification failures, emergency revoke failures, schedule
  conflicts, missing scheduled sessions, API logging, and permission-set naming.

### Scope and risk

- Runtime behavior changes affect Executor, Expiry, and Email Approval in every environment after
  deployment.
- Terraform adds Scheduler resources, Scheduler and legacy-revoke IAM permissions, an API Gateway
  account logging role, and access logs. No secret structure or duration tier changed.
- Permission-set name changes are expected to force replacement; a SIT plan must be reviewed for
  live-session impact before any human apply.
- UAT and PROD remain gated on an approved active-session credential revocation design; membership
  removal alone cannot invalidate already-issued credentials.

### Verification

- `pytest --cov=infrastructure/shared --cov=infrastructure/lambda_functions` passed with 96 tests
  and 78% aggregate coverage.
- `flake8 infrastructure` passed.
- `mypy infrastructure/lambda_functions infrastructure/shared infrastructure/scripts` passed.
- `pylint` passed the configured 8.0 threshold with a score of 8.87/10.
- `terraform fmt -recursive` and `terraform validate` passed.
- Lambda package build and SIT plan were not run because no WSL distribution or Docker daemon is
  available for a Linux-compatible dependency layer.
- Black could not be completed locally because Black 24.1.1 hangs under the available Python
  3.12.14 runtime; CI must confirm formatting under its pinned Python 3.12 environment.

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
- Reformatted the IAM regression test path expression after the first GitHub Actions Black check
  reported that the file would be reformatted.

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
- A GitHub Actions rerun is pending to confirm the Black formatting correction.

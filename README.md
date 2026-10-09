# Production Access Request Portal

A serverless Just-in-Time (JIT) access platform for granting time-limited,
approved access to AWS accounts through Jira and AWS IAM Identity Center.

The project follows a group-based access model: Terraform creates permanent
permission sets, access groups, and account assignments, while runtime Lambda
functions only add or remove users from those groups.

## Architecture

```text
Jira request and approval
        |
        v
API Gateway -> Executor Lambda -> IAM Identity Center group membership
                         |
                         v
                  DynamoDB session with TTL
                         |
                         v
DynamoDB Stream -> Expiry Lambda -> Remove group membership

Optional email approval:
Jira -> Email Approval Lambda -> SES -> Signed approval link -> Jira API
```

The stack targets `ap-southeast-1` and uses API Gateway, Lambda, DynamoDB,
Secrets Manager, SES, CloudWatch, CloudTrail, and IAM Identity Center.

## Security Model

- Zero standing production privileges.
- Explicit Jira approval before access is granted.
- Time-limited access with a maximum duration of 12 hours.
- API key, HMAC validation, JSON schema validation, IAM, and audit logging.
- Separate Lambda IAM roles and environment-specific Terraform state.
- Runtime code changes group membership only; it does not create account
  assignments dynamically.
- Failed or ambiguous requests fail closed.

## Repository Layout

```text
.github/workflows/          GitHub Actions CI and Terraform deployment
infrastructure/terraform/   Terraform root modules and environment config
infrastructure/terraform/modules/
                            Reusable AWS infrastructure modules
infrastructure/lambda_functions/
                            Lambda handlers
infrastructure/shared/      Shared Lambda layer and business logic
infrastructure/scripts/     CI and post-deployment helpers
infrastructure/tests/       Unit tests
```

## CI/CD

GitHub Actions is the preferred deployment path.

The CI workflow runs:

- Black, Flake8, Pylint, and Mypy.
- Pytest with coverage.
- Lambda package creation.
- Terraform formatting and validation.

The deployment workflow uses GitHub OIDC instead of long-lived AWS access
keys. Each target environment has separate plan and apply roles, state, secrets,
and approval controls. The workflow sequence is:

```text
quality gates -> Lambda artifacts -> Terraform plan -> human approval -> apply
```

Terraform plan artifacts are encrypted, raw plan/apply output is withheld from
logs, and apply uses the exact saved plan from the same workflow run.

## Local Validation

Python 3.12 and Terraform 1.9.8 are used by CI.

```bash
python -m pip install -r requirements-dev.txt
black --check infrastructure
flake8 infrastructure
pylint infrastructure/lambda_functions infrastructure/shared infrastructure/scripts
mypy infrastructure/lambda_functions infrastructure/shared infrastructure/scripts
pytest --cov=infrastructure/shared --cov=infrastructure/lambda_functions
```

Build Lambda artifacts on Linux or WSL before Terraform validation:

```bash
cd infrastructure
bash ./build_lambda_packages.sh
cd ..

terraform -chdir=infrastructure/terraform fmt -check -recursive
terraform -chdir=infrastructure/terraform init -backend=false -input=false
terraform -chdir=infrastructure/terraform validate
```

## Deployment Status

The CI/CD definitions and Terraform validation are implemented. AWS deployment
still requires environment-specific GitHub Environments, OIDC roles, remote
state bootstrap, protected secrets, and a reviewed SIT plan.

Local `*.tfvars` files are intentionally untracked because they may contain AWS
account identifiers. CI renders the selected environment's tier and audit
settings together with protected GitHub Environment secrets at runtime.

Do not deploy UAT or production until the DynamoDB TTL revocation timing and
active-session credential revocation controls have an approved production
design.

## Deployment Safety

- Start with SIT.
- Review every plan for replacements or destroys.
- Never commit Terraform state, plans, Lambda packages, credentials, account
  identifiers, or environment secret values.
- Require human approval before apply.
- Refresh the access-group mapping after a successful apply.

No Terraform apply is performed automatically by repository setup or CI checks.
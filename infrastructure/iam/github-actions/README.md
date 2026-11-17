# SIT GitHub OIDC Policies

These templates provide the permissions required by the existing GitHub Actions
Terraform workflow. They do not create OIDC providers or roles and contain no real AWS
account identifiers.

## Render

Run from the repository root:

```powershell
python infrastructure/scripts/render_sit_oidc_policies.py
```

The renderer prompts without echoing for:

- the deployment AWS account ID;
- the IAM Identity Center instance ID (`ssoins-...`);
- the Identity Store ID;
- the exact IAM Identity Center SAML provider ARN (`AWSSSO_..._DO_NOT_DELETE`);
- the allowed target AWS account IDs, defaulting to the deployment account.

The renderer rejects a SAML provider from a different account. Use the account that
contains `pa-sit-github-plan` and `pa-sit-github-apply` as the deployment account; list
separate application accounts only when prompted for target account IDs.

Before rendering, retrieve the values from the same authenticated deployment account:

```bash
aws sts get-caller-identity --query Account --output text
aws iam list-saml-providers \
  --query 'SAMLProviderList[?contains(Arn, `AWSSSO_`) && contains(Arn, `DO_NOT_DELETE`)].Arn' \
  --output text
```

Paste the complete SAML provider ARN when prompted. The renderer inserts it as-is and
will reject both a duplicated `saml-provider/arn:...` prefix and an account mismatch.

Rendered policies are written to
`infrastructure/iam/github-actions/generated/`, which is ignored by Git. If
`--output-dir` is used, the custom location is not automatically ignored.

## Attachments

Create customer-managed policies from the rendered JSON and attach these to
`pa-sit-github-plan`:

- `sit-backend-plan-policy.json`
- `sit-resource-read-policy.json`

Attach these to `pa-sit-github-apply`:

- `sit-backend-apply-policy.json`
- `sit-resource-read-policy.json`
- `sit-apply-iam-lambda-policy.json`
- `sit-apply-data-identity-policy.json`
- `sit-apply-edge-observability-policy.json`

When refreshing AWS policies, replace each customer-managed policy document with the
corresponding rendered JSON and set the new policy version as default. Do not merge
individual statements into an older document; doing so can retain stale account IDs or
omit newly required permissions.

The data/identity policy permits IAM Identity Center to provision only roles under the
regional `aws-reserved/sso.amazonaws.com` path whose names start with
`AWSReservedSSO_pa-sit-`. Managed-policy attachment is further restricted to the three
approved JIT policies: `ReadOnlyAccess`, `PowerUserAccess`, and `AdministratorAccess`.

Do not attach `AdministratorAccess`, `PowerUserAccess`, or `IAMFullAccess`.
Discovery actions that do not support resource-level authorization retain
`Resource: "*"` with explicit action lists. Identity Center mutations are scoped to
the rendered instance, store, and target accounts. Group and permission-set IDs do not
exist before bootstrap, so their wildcard ID patterns should be narrowed after the first
successful deployment where operationally practical.

The backend bucket and lock table must already exist. These policies permit state use,
not backend creation. API Gateway resource IDs also do not exist before bootstrap; its
management paths should be narrowed after the first successful deployment where the API
supports resource-level authorization.

The current SIT backend uses
`sb-sit-terraform-state-ap-southeast-1-52123818`. The suffix is the supported
`state_bucket_name` bootstrap override because the unsuffixed S3 name was already taken
globally. Keep `backend/sit.hcl` and both backend policy templates synchronized if this
name changes.

## Residual Security Boundary

The apply role can write inline policies and trust policies on the three Lambda
execution roles and can deploy Lambda code that assumes those roles. Exact role-name
scoping prevents direct modification of the GitHub deployment roles, but it is not a
complete privilege-escalation boundary. The protected `sit-apply` Environment and
human approval are mandatory controls. A future permissions-boundary or SCP design is
required for a stronger technical boundary.

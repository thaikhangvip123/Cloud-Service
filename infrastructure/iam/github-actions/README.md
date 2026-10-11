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
- the allowed target AWS account IDs, defaulting to the deployment account.

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

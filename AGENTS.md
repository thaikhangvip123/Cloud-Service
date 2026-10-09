# AGENTS.md — Production Access Request Portal

> Instructions for AI coding agents (Claude Code, Codex, Cursor, Copilot, etc.) working in this repository.
> Human-facing documentation lives in `docs/`. This file is the **operating manual for agents**: read it fully before making changes.
> Source of truth: Project Document v2.0 (Group-Based Access Architecture), dated 2026-03-01.

---

## 0. Language and communication

- Write code, comments, commit messages, Terraform, and this repo's docs in **English** unless a file is already in Vietnamese (e.g. `docs/HƯỚNG_DẪN_HIỂU_DỰ_ÁN_IAC.md`).
- When talking to a human who writes in Vietnamese, **reply in Vietnamese**. Keep identifiers, commands, and AWS terms in English.
- Be explicit about uncertainty. If you did not run a command or test, say so. Never claim "tested", "applied", or "verified" without evidence from actual output.

---

## 1. What this system is (30-second version)

A **Just-in-Time (JIT) access** system for AWS production accounts. Fully serverless, region `ap-southeast-1`.

```
Jira (request + approval) → API Gateway → Lambda Executor → IAM Identity Center (add user to group)
                                                         → DynamoDB (session record with TTL)
DynamoDB TTL delete → DynamoDB Stream → Lambda Expiry → IAM Identity Center (remove user from group)
Email approval (optional): Jira → Lambda Email Approval → SES → approver clicks link → Jira Approval API
```

**Core mechanism (v2.0): Group-Based Access.** Groups, permission sets, and group→account assignments are **permanent and created once by Terraform**. At runtime Lambdas only **add/remove group memberships**. Never create or delete account assignments at runtime. That was the v1.0 (Direct Assignment) design and it is deprecated.

### Design principles (every change must preserve these)

1. **Zero Standing Privileges**: no permanent production access; every grant is time-boxed and approved.
2. **Least Privilege**: three access types (ReadOnly, PowerUser, Admin), per-Lambda IAM roles, ARN-scoped policies.
3. **Defense in Depth**: SSO + API key + HMAC + IAM + audit logging. Never remove a layer because another one "already covers it".
4. **Fail-Safe Defaults**: deny by default. Grant only after explicit approval **and** successful provisioning. On any ambiguity or error, do not grant.
5. **Complete Auditability**: every action is logged (Jira, CloudWatch, CloudTrail, DynamoDB as per the audit matrix).

---

## 2. Repository map

```
infrastructure/
├── build_lambda_packages.sh            # builds Lambda zips + dependencies layer
├── scripts/populate_access_group_mapping.py   # Terraform outputs → Secrets Manager mapping
└── terraform/
    ├── main.tf                         # root orchestration (dependency order matters)
    ├── variables.tf  locals.tf  outputs.tf
    ├── iam.tf                          # Lambda IAM roles/policies
    ├── jit_access_additions.tf         # group-based access modules + policies
    ├── backend_setup.tf  providers.tf  versions.tf
    ├── service-limits-validation.tf    # pre-apply AWS limit checks
    ├── backend/{sit,uat,prod}.hcl      # remote state config per env
    ├── env/{sit,uat,prod}.tfvars       # per-env values
    └── modules/
        api-gateway, dynamodb, dynamodb-approval-tokens, identity-center,
        identity-center-permission-sets, identity-center-access-groups,
        identity-center-group-assignments, lambda-functions, secrets-manager, ses

lambda_functions/{executor,expiry,email_approval}/handler.py   # thin handlers
shared/                                                          # Lambda Layer (python/shared/)
├── jit_access.py          # JITAccessManager — core group operations
├── jira_client.py         # Jira REST client
├── secrets.py             # Secrets Manager helper (module-level cache)
├── webhook_auth.py        # API key + HMAC + JSON schema validation
├── account_mapping.py     # account name ↔ ID
├── dynamodb_session.py    # session persistence
├── identity_center.py     # Identity Center API wrapper
├── email_notification.py  # SES notifications
├── logging_config.py      # structured JSON logging + correlation_id
├── config.py              # feature flags
└── utils.py
docs/                      # LAMBDA_ARCHITECTURE, GROUP_BASED_ACCESS_MECHANISM,
                           # ACCESS_GROUP_MAPPING_MECHANISM, EMAIL_APPROVAL_MECHANISM,
                           # SES_CONFIGURATION, HƯỚNG_DẪN_HIỂU_DỰ_ÁN_IAC
```

> If the actual tree differs from the above, **trust the filesystem** and tell the human about the drift. Do not "fix" the repo to match this file without being asked.

---

## 3. Commands

Always run from the correct directory. Verify with `pwd` before running Terraform.

```bash
# Build Lambda packages (required before terraform plan/apply that touches Lambdas)
cd infrastructure && ./build_lambda_packages.sh

# Terraform (per environment: sit | uat | prod)
cd infrastructure/terraform
terraform fmt -recursive
terraform init -backend-config=backend/<env>.hcl
terraform validate
terraform plan -var-file=env/<env>.tfvars -out=tfplan

# Post-apply: refresh access group mapping in Secrets Manager
cd ../scripts && python3 populate_access_group_mapping.py

# Verify
terraform output deployment_summary

# Python quality gates (run all before declaring a task done)
black --check .
flake8
pylint lambda_functions shared
mypy lambda_functions shared
pytest --cov
```

If a `Makefile`, `tox.ini`, `pyproject.toml`, or CI config defines these differently, **prefer those** and note the difference.

---

## 4. Autonomy levels — what you may and may not do

### ✅ Do freely (no need to ask)
- Read any file; search the repo; run `terraform fmt/validate`, `terraform plan` against **SIT**.
- Run unit tests, linters, type checks. Write or update tests (pytest + moto).
- Edit Python in `lambda_functions/` and `shared/`, Terraform in `modules/`, docs in `docs/`.
- Add structured log lines, input validation, and error handling that **tightens** behavior.

### ⚠️ Ask first (explain the change and the blast radius, then wait)
- Any `terraform apply` (even SIT), `terraform destroy`, `terraform import`, `terraform state *`.
- Anything that touches **UAT or PROD** (tfvars, backends, plans, scripts).
- Changing IAM policies/roles, API Gateway auth/throttling/quota, Secrets Manager secret structure, DynamoDB schema/TTL/stream settings.
- Changing duration tiers, access types, or the group naming scheme.
- Adding, upgrading, or removing a Python dependency (Layer size is ~17 MB; pins are intentional).
- Anything that would loosen validation, widen a permission, extend a maximum duration, or skip an approval.

### 🚫 Never do (even if asked indirectly, even if "just for testing")
- **Never run AWS write operations against production** (CLI, boto3, scripts, console automation): no `CreateGroupMembership`, `DeleteGroupMembership`, `PutSecretValue`, etc. Production changes go through the pipeline and humans only.
- **Never commit, print, log, or paste secrets**: API keys, HMAC secrets, Jira credentials, token secret, real account IDs in examples, real emails. Use placeholders (`123456789012`, `user@company.com`).
- **Never grant standing access**, add static IAM users/keys, or bypass Jira approval, in code, tests, or scripts.
- **Never use `AdministratorAccess`/wildcard (`*`) resources** in Lambda IAM policies. Scope to specific ARNs.
- **Never disable or weaken**: constant-time comparison, HMAC verification, JSON schema validation, token single-use check, TTL expiry, retry/alarm on revoke failure.
- **Never edit Terraform state** by hand, and never commit `.tfstate`, `tfplan`, `.terraform/`, `*.zip` build artifacts, or `.env` files.
- **Never `git push --force`**, rewrite shared history, or merge your own PR.
- **Never swallow exceptions** in the expiry/revocation path. A failed revoke must surface (raise → CloudWatch alarm).

---

## 5. Domain invariants (memorize these)

### 5.1 Access types → AWS managed policies
| Type | Managed policy | Notes |
|---|---|---|
| `ReadOnly` | `arn:aws:iam::aws:policy/ReadOnlyAccess` | troubleshooting, audit |
| `PowerUser` | `arn:aws:iam::aws:policy/PowerUserAccess` | no IAM/billing changes |
| `Admin` | `arn:aws:iam::aws:policy/AdministratorAccess` | emergency only |

### 5.2 Duration → tier (always round UP; never round down)
| Requested hours | Tier | Session duration |
|---|---|---|
| 0.5 – 1.0 | `1h` | `PT1H` |
| 1.1 – 2.0 | `2h` | `PT2H` |
| 2.1 – 4.0 | `4h` | `PT4H` |
| 4.1 – 8.0 | `8h` | `PT8H` |
| 8.1 – 12.0 | `12h` | `PT12H` |
| > 12.0 | **reject** | request fails |

- Max 12h is hard-coded in code; do not raise it without explicit human approval.
- Tiers actually deployed depend on the env (see §9). A request that maps to a tier **not deployed in that env must fail closed** with a clear error, never silently fall back to a different tier.

### 5.3 Resource formulas
```
Permission Sets  = |access_types| × |duration_tiers|
Access Groups    = N_accounts × |access_types| × |duration_tiers|
Group Assignments = Access Groups
```
Example: 2 accounts × 3 types × 3 tiers → 9 permission sets, 18 groups, 18 assignments.

### 5.4 Naming conventions
- Resource prefix: `pa-{environment}`; resources: `{resource_prefix}-{component}-{region}`.
  - `pa-sit-executor-ap-southeast-1`, `pa-sit-access-sessions-ap-southeast-1`, `pa-sit-api-ap-southeast-1`
- Access group name: `pa-{env}-{account}-{type}-{tier}` → `pa-sit-application-PowerUser-2h`
- Access group **mapping key**: `{account_name}-{access_type}-{duration_tier}` (e.g. `application-PowerUser-2h`)
- DynamoDB `sessionId`: `membership-{membership_id}`
- Terraform state: bucket `sb-{env}-terraform-state-{region}`, lock table `sb-{env}-terraform-lock-{region}`, key `{project_name}/{environment}/terraform.tfstate`

### 5.5 Data model (do not change attribute names without a migration plan)
- **AccessSessions** (PK `sessionId`): `requestId, requester, awsAccountId, account_name, access_type, duration_hours, duration_tier, group_id, group_name, membership_id, permission_set_arn, granted_at, expires_at, ttl, status (Active|Expired|Revoked)`. On-demand billing, stream `NEW_AND_OLD_IMAGES`, TTL on `ttl`, encrypted.
- **ApprovalTokens** (PK `token_id`): `request_id, action (approve|decline), created_at, expires_at (+24h), used, used_at, ttl`.
- **Access group mapping secret**: `{"access_groups": {"<key>": {group_id, group_name, account_name, account_id, access_type, duration_tier, permission_set_arn}}}`. Produced by `populate_access_group_mapping.py` from Terraform outputs. **Never hand-edit it.**
- `membership_id` is **required** on a group-based session: it is what revocation uses. A session without it is legacy (direct assignment) and takes the legacy path in Lambda Expiry.

### 5.6 Security-critical behaviors
- Webhook auth: `x-api-key` validated against Secrets Manager with **constant-time comparison**; payload integrity via HMAC-SHA256; JSON schema validation. API Gateway also enforces API key + usage plan (burst 20, rate 10 req/s default, 10,000/day).
- Email approval token format: `{token_id}.{expiry_timestamp}.{hmac_signature}` (HMAC-SHA256, key from Secrets Manager). Rules: verify signature → check expiry → check `used` → **mark used before** calling Jira → single-use, 24h TTL.
- Lambda Expiry retry on `DeleteGroupMembership`: attempts at 0s, +1s, +2s, +4s (exponential backoff). After the final failure: **raise** so the CloudWatch alarm fires.
- Lambda Expiry must verify the stream record is a **TTL deletion** (`eventName == REMOVE` and `userIdentity.principalId == dynamodb.amazonaws.com`), not a manual delete.
- Emergency revoke: list memberships for the user (`ListGroupMembershipsForMember`), delete all, record the event in DynamoDB and CloudWatch.

---

## 6. Task playbooks

For each task: **read the listed files first**, make the smallest change that works, run the checks, then report.

### 6.1 Modify a Lambda handler or shared module
1. Read the handler, the relevant `shared/` modules, and `docs/LAMBDA_ARCHITECTURE.md`.
2. Keep handlers **thin**; business logic belongs in `shared/`. Shared code is deployed via the Layer, so **a `shared/` change affects all three Lambdas**: check every caller (`grep -rn "<symbol>"`).
3. Preserve the correlation ID flow (§7.3) and structured logging.
4. Update or add unit tests (moto). Cover success, validation failure, AWS error, and retry paths.
5. If you add an AWS API call: update the **specific Lambda's** IAM policy in `iam.tf` with the least-privilege action + ARN, and mention it in the PR. Never share roles between Lambdas.
6. Rebuild packages with `build_lambda_packages.sh` if you changed dependencies; keep function code small (~76 KB) and the Layer ~17 MB.

### 6.2 Add a new AWS account
1. Add the entry to `target_accounts` in `env/<env>.tfvars` (`{"<key>": {account_id, account_name}}`).
2. `terraform plan` (SIT) and review: expect new groups + assignments only; **no destroys**.
3. Human applies. Then run `populate_access_group_mapping.py` (mapping refresh; remember the 5-minute Lambda cache).
4. Add the account name to the Jira custom field options (human step; list it in your report).
5. Test end-to-end in SIT with a test request.
6. Re-check service limits (§9) before suggesting PROD.

### 6.3 Add a new access type
1. Add to `access_types` in tfvars.
2. Update the `managed_policies` map in `modules/identity-center-permission-sets/main.tf`.
3. Check variable validation in `variables.tf` and the schema in `webhook_auth.py` that accepts access types.
4. Plan → human apply → populate mapping → test.
5. Recompute counts with §5.3 and confirm limits.
6. **Ask first** if the new type maps to a broad policy.

### 6.4 Add or change a duration tier
Touches: tfvars `duration_tiers`, `map_duration_to_tier` in `jit_access.py`, permission set session durations, validation, tests, docs table in §5.2. Always **ask first**. Keep round-up semantics and the 12h cap.

### 6.5 Change Terraform / IAM
- Respect the module order in `main.tf`: `identity_center` → (`permission_sets`, `access_groups`, `secrets_manager`) → `group_assignments` → (`lambda_functions`, `dynamodb`, `dynamodb_approval_tokens`) → `api_gateway`. Do not introduce circular dependencies.
- Every new variable needs a `type`, `description`, and **`validation`** block when input can be wrong.
- Never replace a resource when an in-place update is possible. Flag any `forces replacement` / destroy in the plan prominently. Replacing an access group or permission set can revoke live sessions.
- Keep `service-limits-validation.tf` updated when you add resources that count against quotas.
- Plans for UAT/PROD are produced and applied by humans/CI only.

### 6.6 Debug a failed grant or revoke
1. Get the `correlation_id` / `request_id` and search CloudWatch Logs Insights (read-only).
2. Check in order: webhook auth → payload parsing → duration→tier → mapping key lookup → user lookup by email in Identity Store → `CreateGroupMembership` → DynamoDB write → Jira update.
3. Common causes: mapping secret stale or missing key; tier not deployed in this env; user email not in Identity Store; Jira credentials expired; Lambda near its 30s timeout.
4. Fix the root cause. Do not add a bypass or a "force grant" path.

### 6.7 Update documentation
Keep `docs/` and this file consistent with the code. Update the project document table(s) when behavior, limits, or naming change. Do not invent numbers: if something is unmeasured, say "not measured".

---

## 7. Coding standards

### 7.1 Python (3.12)
- Tooling: **black**, **flake8**, **pylint**, **mypy** (+ boto3-stubs). Type-annotate all new functions. No new lint suppressions without a comment explaining why.
- Pinned deps (do not bump casually): boto3 1.34.34, requests 2.31.0, jsonschema 4.21.1; dev: pytest 8.0.0, moto 5.0.0, pytest-cov 4.1.0.
- Use the shared modules; do not call `boto3.client("secretsmanager")` ad hoc: go through `secrets.py` (with caching) and `identity_center.py`.
- Create boto3 clients at module level (reused across warm invocations); never inside hot loops.
- Never hard-code account IDs, ARNs, group IDs, emails, or secret values. Config comes from env vars, Secrets Manager, or the mapping.
- Timestamps: ISO 8601 UTC strings for `granted_at/expires_at`; Unix epoch seconds for `ttl`.
- Handle AWS errors explicitly by error code (`ResourceNotFoundException`, `AccessDeniedException`, `InvalidRequestException`, throttling, `ConflictException` for already-a-member). Make grant operations **idempotent** (a webhook retry must not create duplicate memberships or sessions or crash).
- Fail closed: when validation fails or the lookup is ambiguous, return an error and grant nothing.
- Timeouts: Lambdas have 30s / 256 MB. Don't add long synchronous waits or retries that can exceed 30s total (the existing 1+2+4s backoff is the budget).

### 7.2 Logging
- Use `logging_config.py` structured JSON logging only. No `print()`.
- Required fields where available: `timestamp, level, message, correlation_id, request_id, operation, requester, aws_account, access_type, duration_hours, duration_tier`.
- **Never log**: API keys, HMAC secrets, full tokens, Jira credentials, full webhook headers, or raw secret values.

### 7.3 Correlation ID
Generate or propagate one `correlation_id` per request and include it in **every** log line and downstream call that supports it (Jira → API Gateway → Executor → Identity Center → DynamoDB → Jira update).

### 7.4 Terraform
- `terraform fmt -recursive` and `terraform validate` must pass.
- Provider/Terraform versions live in `versions.tf` (Terraform ≥ 1.0); do not loosen constraints.
- Tag and name resources with the §5.4 convention. Use `locals.tf` for computed names.
- No inline secrets in `.tf`/`.tfvars`. Secret **values** are managed outside Git.
- Prefer module outputs over duplicated data lookups. Keep outputs useful for `populate_access_group_mapping.py`; **do not rename or remove outputs it consumes** without updating the script.

---

## 8. Testing and "definition of done"

A task is done only when **all** are true:

- [ ] `black --check`, `flake8`, `pylint`, `mypy` pass (or failures are pre-existing and listed).
- [ ] `pytest --cov` passes; new/changed logic has tests (moto for AWS). Security-relevant paths (auth failure, expired/used token, invalid tier, missing mapping key, revoke retry exhaustion) have **negative tests**.
- [ ] `terraform fmt`, `terraform validate` pass; `terraform plan` (SIT) reviewed: **no unintended destroy/replace**.
- [ ] No new secrets, IDs, or emails in code, logs, tests, or docs.
- [ ] IAM changes are least-privilege and listed in the summary.
- [ ] Docs updated if behavior, naming, limits, or workflow changed.
- [ ] Final report follows §11.

Testing guidance:
- Unit tests must not hit real AWS. Use moto; mock Jira with `requests` mocking.
- Cover: duration boundaries (0.5, 1.0, 1.1, 2.0, 2.1, 4.0, 4.1, 8.0, 8.1, 12.0, 12.1), idempotent re-grant, user-not-found, mapping cache expiry, TTL-delete vs manual-delete stream events, legacy vs group-based session branch, SES failure not blocking the access flow.

---

## 9. Environments

| Setting | SIT | UAT | PROD |
|---|---|---|---|
| Duration tiers | 1h, 2h, 4h | 1h, 2h, 4h, 8h | 1h, 2h, 4h, 8h, 12h |
| DynamoDB PITR | off | on | on |
| Log retention | 7 d | 14 d | 90 d |
| API rate limit | 10 req/s | 10 req/s | 50 req/s |
| SES | Sandbox | Sandbox | Production |

- Each environment is fully independent (own backend, tfvars, state, secrets).
- **Default target for any experiment is SIT.** Do not point at UAT/PROD unless a human explicitly instructs you, and even then only for read-only operations.
- Before any Terraform command, confirm the backend/tfvars pair match the intended environment. A mismatched `-backend-config` and `-var-file` is a serious incident risk.

### AWS service limits to respect
| Service | Default limit | This project |
|---|---|---|
| Identity Center groups | 100,000 | N × types × tiers (usually < 100) |
| Permission sets | 2,000 | types × tiers (15 at max) |
| Provisioned permission sets per account | 50 | types × tiers (15 at max) |
| Lambda concurrency | 1,000 | < 10 expected |

---

## 10. Observability and alarms (don't break these)

| Metric | Threshold |
|---|---|
| Lambda error rate | > 5% / 5 min |
| Lambda duration | > 25 s (close to the 30 s timeout) |
| API Gateway 4xx | > 20% / 15 min |
| API Gateway 5xx | > 1% / 5 min |
| DynamoDB throttled requests | > 0 |
| SES bounce / complaint | > 5% / > 0.1% |
| Failed token validations | > 10 / hour |

Audit matrix: access provisioned, access expired, and emergency revocation must be recorded in **Jira, CloudWatch, CloudTrail, and DynamoDB**. Authentication failures must be in CloudWatch and CloudTrail. If you add a new privileged action, add it to this matrix and make sure it is logged.

Known external-dependency behavior (keep it that way):
- **SES failure** → notification fails, the access flow continues.
- **Jira failure** → status update fails and is retried; it must not block the AWS-side grant/revoke logic once approved/expired.
- **Secrets Manager down** → Lambdas fail (cached values keep working on warm instances). Do not add fallbacks to hard-coded values.
- **Identity Center failure** → cannot grant or revoke. Never report a grant as successful if group membership was not created.

---

## 11. How to report your work

End every task with a short summary containing:

1. **What changed** (files, 1 line each).
2. **Why**, and which design principle/invariant it relates to.
3. **Verification actually performed**: commands run and results. Say explicitly what you did *not* run.
4. **Risk / blast radius**: affected Lambdas, environments, IAM, anything that could affect live sessions.
5. **Human follow-ups**: `terraform apply`, mapping refresh, Jira field update, secret rotation, etc.
6. **Open questions or discrepancies** found (see §12).

Commit and PR conventions: small, focused commits; imperative subject line ≤ 72 chars (`Add idempotency check to CreateGroupMembership`); PR description includes the §11 summary and the Terraform plan summary (resources to add/change/destroy) when infra changes. Never merge to `main` without human review.

---

## 12. Known caveats and ambiguities (verify before relying on them)

These come from the project document. Treat them as **things to check**, and raise them with a human instead of silently "resolving" them.

1. **The "< 60 s" SLA is not end-to-end.** It describes credential invalidation *after* `DeleteGroupMembership`. Expiry depends on DynamoDB TTL deletion, which is **not real-time** (AWS documents it as a background process; deletion can lag after the TTL timestamp). The permission set `Session Duration` (PT1H…PT12H) is the hard backstop. Do not state or document "revoked within 60 s of expiry" without this nuance, and flag any design that relies on TTL for time-critical revocation.
2. **Sub-0.5h requests.** §5.2 starts at 0.5h, while the limits section says any value > 0 is supported (0.1h = 6 minutes). Confirm intended behavior (map to `1h`? reject?) before changing `map_duration_to_tier`.
3. **Terraform state naming** uses the `sb-` prefix while resources use `pa-`. Confirm this is intentional before renaming anything.
4. **Module count**: the doc says 9 modules but lists 10 (`identity-center`, `permission-sets`, `access-groups`, `group-assignments`, `api-gateway`, `dynamodb`, `dynamodb-approval-tokens`, `lambda-functions`, `secrets-manager`, `ses`). Trust the filesystem.
5. **`env/uat.tfvars` and `env/prod.tfvars`** are referenced but the documented tree only shows `sit.tfvars`. Do not create them from guesswork; ask.
6. **Executor IAM** lists `identitystore:UpdateUser` / `DescribeUser` "for immediate revocation" (`immediate_revoke_with_user_tag`) while Expiry holds `DeleteGroupMembership`. Review who truly needs what before adding or removing permissions.
7. **Mapping cache (5 min)**: after `populate_access_group_mapping.py` runs, warm Lambdas can serve the old mapping for up to 5 minutes. Account for this in tests and rollout steps.
8. **Legacy sessions**: Lambda Expiry still has a legacy (direct assignment) branch. Do not remove it without confirming no legacy sessions remain.

---

## 13. When in doubt

- Prefer the **safer** option: deny, fail closed, ask.
- Prefer the **smaller** change: no drive-by refactors, no renames, no dependency bumps unrelated to the task.
- Prefer **evidence** over assumptions: read the code, run the tests, quote the output.
- If a request conflicts with this file or the five design principles, **stop and explain the conflict** instead of working around it.
# PA SIT JIT Bridge

Forge Automation Action that forwards an approved Jira Service Management request to the existing
SIT AWS JIT access API. AWS remains responsible for authentication validation, Identity Center group
membership, expiry scheduling, session persistence, Jira status updates, and notifications.

## Security contract

The function sends the exact JSON body used to calculate the timestamped HMAC signature. It preserves
all authentication layers expected by the Executor Lambda:

- API Gateway API key in `x-api-key`.
- Unix timestamp in `x-request-timestamp`.
- HMAC-SHA256 in `x-jira-signature`.

Do not put secret values in this repository. Configure them as encrypted Forge variables.

## Local verification

Run from this directory:

```powershell
npm install
npm test
forge lint
```

## Development environment variables

Run from this directory. Omit each value so Forge prompts for it without placing it in PowerShell
history.

```powershell
forge variables set -e development AWS_JIT_ENDPOINT
forge variables set --encrypt -e development AWS_JIT_API_KEY
forge variables set --encrypt -e development WEBHOOK_HMAC_SECRET
forge variables list -e development
```

`AWS_JIT_API_KEY` and `WEBHOOK_HMAC_SECRET` must match the existing SIT webhook authentication
secret consumed by the Executor Lambda. Creating unrelated replacement values only in Forge will
cause authentication failures.

## Deploy and install

Deployment changes Atlassian-hosted state. Review the app and variables before running:

```powershell
forge deploy --non-interactive -e development
forge install --non-interactive --site <your-site>.atlassian.net --product jira --environment development
```

Use `--upgrade` instead of a new installation when the development app is already installed and its
permissions or egress declarations changed.

## Jira Automation configuration

Add **Provision approved AWS JIT access** after the approval transition and map these inputs using
Jira smart values:

| Action input | Expected value |
| --- | --- |
| `Request ID` | Jira request key, normally `{{issue.key}}` |
| `Requester email` | Email that matches the IAM Identity Center user |
| `AWS account name` | Logical account name from the access-group mapping |
| `Access type` | `ReadOnly`, `PowerUser`, or `Admin` |
| `Duration hours` | Numeric requested duration, no more than 12 |

Do not hard-code the Jira project key, request type ID, workflow status ID, or custom field IDs in
the Forge backend. Those values belong in the Jira Automation rule so the app can later move from the
Support test project to a dedicated service project.

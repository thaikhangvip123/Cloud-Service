# Development Environment Handoff

This document is the setup checklist for continuing the SIT JIT access work on another Windows
device. It covers the repository, the Atlassian Forge bridge, Python tooling, AWS CLI/SSO, and
Terraform. It intentionally contains no API keys, HMAC secrets, account IDs, real email addresses,
or credentials.

## 1. Repository and branch

Install Git for Windows with Git Credential Manager enabled, then clone and switch to the working
branch:

```powershell
git clone https://github.com/thaikhangvip123/Cloud-Service.git
cd Cloud-Service
git switch feature/sit-jit-integration
```

GitHub does not accept account passwords for Git operations. If push or pull authentication fails,
use Git Credential Manager:

```powershell
git credential-manager github list
git credential-manager github login
```

Use the browser flow and sign in with a GitHub account that has write access to the repository.
Never paste a GitHub token into source files, shell scripts, documentation, or chat messages.

## 2. Required local tools

Use these versions for the current SIT work:

| Tool | Version or constraint |
| --- | --- |
| Git for Windows | Current supported release |
| Python | 3.12 |
| Node.js | 24.22.1 for local Forge work |
| npm | Version bundled with Node 24.22.1 |
| Forge CLI | 15.1.0 |
| Terraform | 1.9.8, matching the CI workflow |
| AWS CLI | AWS CLI v2 |

The Forge app also declares the Node versions supported by Forge CLI 15.1.0 in its `package.json`:

```text
^22.23.4 || ^24.22.1 || >=26.12.1
```

## 3. Node.js and Forge CLI

Install `fnm`, start a PowerShell session with `fnm` enabled, and select the project Node version.
Node 24.22.1 satisfies Forge CLI 15.1.0's package engine and is in the Node 22/24 range that the CLI
reports as supported. Do not use Node 26 as the default even though the package engine accepts newer
versions; Forge CLI warns that Node 26 behavior is not guaranteed.

```powershell
fnm install 24.22.1
fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression
fnm use 24.22.1
node --version
npm --version
```

To initialize `fnm` automatically in new PowerShell sessions, add this line to `$PROFILE`:

```powershell
fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression
```

Install Forge CLI under Node 24.22.1 and verify that the active terminal is not resolving an older
global installation from another Node version:

```powershell
npm install -g @forge/cli@15.1.0
Get-Command forge -All
forge --version
```

Expected Forge CLI version:

```text
15.1.0
```

## 4. Forge application dependencies

Run Forge commands from the Forge app root only:

```powershell
cd integrations/pa-sit-jit-bridge
npm ci
npm test
forge login
forge lint
```

`npm ci` uses the committed `package-lock.json` and reproduces the reviewed dependency tree. Do not
copy `node_modules` from the previous device and do not run `npm audit fix --force`.

The app is already installed on the Jira development site. A new device does not normally need to
run `forge install` again. Run an installation upgrade only after scopes or egress permissions in
`manifest.yml` change:

```powershell
forge install --non-interactive --upgrade --site <site>.atlassian.net --product jira --environment development
```

## 5. Forge environment variables

Forge variables are stored by Atlassian against the app ID and the `development` environment. They
are not stored in Git or local project files. After signing in with the same Atlassian account,
verify their presence:

```powershell
forge variables list -e development
```

Required variables:

| Variable | Storage requirement |
| --- | --- |
| `AWS_JIT_ENDPOINT` | Full HTTPS SIT API Gateway `/sit/provision-access` endpoint |
| `AWS_JIT_API_KEY` | Encrypted Forge variable |
| `WEBHOOK_HMAC_SECRET` | Encrypted Forge variable |

Encrypted values are displayed as `****` and cannot be retrieved as plaintext. If either secret is
rotated, set the replacement value through the Forge prompt rather than placing it in shell history:

```powershell
forge variables set --encrypt -e development AWS_JIT_API_KEY
forge variables set --encrypt -e development WEBHOOK_HMAC_SECRET
```

`WEBHOOK_HMAC_SECRET` must remain identical in Forge development, the corresponding AWS Secrets
Manager field, and the GitHub SIT environment secret. The API Gateway API key and HMAC secret are
different credentials and must not be interchanged.

Variable changes affect deployed functions only after a new deployment:

```powershell
forge deploy --non-interactive -e development
```

An existing tunnel keeps the variables loaded when it started. Stop and restart the tunnel after a
variable change:

```powershell
forge tunnel -e development
```

## 6. Python environment

From the repository root, create a fresh Python 3.12 virtual environment and install both runtime
and development dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r infrastructure/requirements.txt
python -m pip install -r requirements-dev.txt
```

Run the repository quality gates from the repository root:

```powershell
black --check .
flake8
pylint infrastructure/lambda_functions infrastructure/shared
mypy infrastructure/lambda_functions infrastructure/shared
pytest --cov
```

Unit tests must not call real AWS services.

## 7. AWS CLI and SIT SSO

AWS CLI profiles and SSO sessions are local machine state and are not transferred through Git.
Configure the approved SIT profile on the new device, sign in, and verify the caller in the same
VS Code terminal that will run Terraform:

```powershell
aws configure sso
aws sso login --profile <sit-profile>
aws sts get-caller-identity --profile <sit-profile>
```

Do not continue if the caller or account is not the intended SIT identity. Do not use static IAM
access keys. UAT and PROD are out of scope for this handoff.

## 8. Terraform initialization and verification

Run Terraform only from `infrastructure/terraform` and keep the SIT backend paired with the SIT
variable file:

```powershell
cd infrastructure/terraform
terraform version
terraform init -reconfigure -backend-config="backend/sit.hcl"
terraform fmt -recursive -check
terraform validate
```

Producing a SIT plan is permitted after verifying the caller and backend pairing:

```powershell
terraform plan -var-file="env/sit.tfvars"
```

Do not run `terraform apply`, `destroy`, `import`, or `terraform state` commands without explicit
human approval. Do not point this checkout at UAT or PROD.

## 9. Files that must remain local or generated

Do not commit or transfer these generated or credential-bearing paths:

```text
.env
.env.*
.venv/
.forge/
node_modules/
.terraform/
*.tfstate
*.tfstate.*
tfplan
*.tfplan
*.log
*.zip
*.pem
*.key
infrastructure/build/
infrastructure/packages/
infrastructure/iam/github-actions/generated/
```

The Forge `manifest.yml`, app ID, API Gateway hostname, `package.json`, and `package-lock.json` are
safe to commit. Secret values are not.

## 10. New-device verification checklist

Before continuing SIT testing, confirm all of the following:

```powershell
git status --short
node --version
npm --version
forge --version
python --version
terraform version
aws --version
```

Then, from the Forge app root:

```powershell
npm ci
npm test
forge lint
forge variables list -e development
forge install list
```

Expected state:

- Node.js is 24.22.1 and Forge CLI is 15.1.0.
- Forge development installation is connected to the intended Jira site.
- `AWS_JIT_ENDPOINT` is a complete HTTPS URL, not only `/sit/provision-access`.
- `AWS_JIT_API_KEY` and `WEBHOOK_HMAC_SECRET` are encrypted and displayed as `****`.
- No secret, Terraform state, build output, tunnel output, or dependency directory appears in
  `git status`.
- The AWS caller is the approved SIT identity before any Terraform or AWS diagnostic command.

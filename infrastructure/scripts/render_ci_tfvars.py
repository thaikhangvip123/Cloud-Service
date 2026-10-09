#!/usr/bin/env python3
"""Render sensitive Terraform inputs from CI environment variables."""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


ACCOUNT_ID_PATTERN = re.compile(r"^\d{12}$")

ENVIRONMENT_VALUES = {
    "sit": {
        "duration_tiers": ["1h", "2h", "4h"],
        "enable_organization_trail": False,
    },
    "uat": {
        "duration_tiers": ["1h", "2h", "4h", "8h"],
        "enable_organization_trail": False,
    },
    "prod": {
        "duration_tiers": ["1h", "2h", "4h", "8h", "12h"],
        "enable_organization_trail": True,
    },
}

REQUIRED_ENV = {
    "admin_email": "CI_ADMIN_EMAIL",
    "ses_sender_email": "CI_SES_SENDER_EMAIL",
    "identity_center_portal_url": "CI_IDENTITY_CENTER_PORTAL_URL",
    "approval_base_url": "CI_APPROVAL_BASE_URL",
    "jira_base_url": "CI_JIRA_BASE_URL",
    "jira_email": "CI_JIRA_EMAIL",
    "jira_api_token": "CI_JIRA_API_TOKEN",
    "api_key_value": "CI_API_KEY_VALUE",
    "webhook_hmac_secret": "CI_WEBHOOK_HMAC_SECRET",
    "approval_token_secret": "CI_APPROVAL_TOKEN_SECRET",
}


def build_tfvars(environ: dict[str, str], environment: str) -> dict[str, Any]:
    if environment not in ENVIRONMENT_VALUES:
        raise ValueError("environment must be sit, uat, or prod")

    missing = [name for name in REQUIRED_ENV.values() if not environ.get(name)]
    if not environ.get("CI_TARGET_ACCOUNTS_JSON"):
        missing.append("CI_TARGET_ACCOUNTS_JSON")
    if missing:
        raise ValueError(f"Missing required CI environment variables: {', '.join(sorted(missing))}")

    try:
        target_accounts = json.loads(environ["CI_TARGET_ACCOUNTS_JSON"])
    except json.JSONDecodeError as exc:
        raise ValueError("CI_TARGET_ACCOUNTS_JSON must be valid JSON") from exc
    if not isinstance(target_accounts, dict) or not target_accounts:
        raise ValueError("CI_TARGET_ACCOUNTS_JSON must contain a non-empty object")
    for account_key, account in target_accounts.items():
        if not isinstance(account_key, str) or not account_key:
            raise ValueError("Each target account key must be a non-empty string")
        if not isinstance(account, dict):
            raise ValueError(f"Target account {account_key!r} must be an object")
        account_id = account.get("account_id")
        account_name = account.get("account_name")
        if not isinstance(account_id, str) or not ACCOUNT_ID_PATTERN.fullmatch(account_id):
            raise ValueError(f"Target account {account_key!r} must use a 12-digit account_id")
        if not isinstance(account_name, str) or not account_name.strip():
            raise ValueError(f"Target account {account_key!r} must use a non-empty account_name")

    values: dict[str, Any] = {
        terraform_name: environ[env_name] for terraform_name, env_name in REQUIRED_ENV.items()
    }
    values.update(ENVIRONMENT_VALUES[environment])
    values["environment"] = environment
    values["aws_region"] = "ap-southeast-1"
    values["target_accounts"] = target_accounts
    return values


def github_mask_commands(values: dict[str, Any]) -> list[str]:
    """Return GitHub commands that mask each target AWS account ID."""
    accounts = values.get("target_accounts", {})
    return [
        f"::add-mask::{account['account_id']}"
        for account in accounts.values()
        if isinstance(account, dict) and account.get("account_id")
    ]


def write_tfvars(output: Path, values: dict[str, Any]) -> None:
    output.write_text(json.dumps(values, separators=(",", ":")), encoding="utf-8")
    if os.name != "nt":
        output.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=sorted(ENVIRONMENT_VALUES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-mask", action="store_true")
    args = parser.parse_args()
    values = build_tfvars(dict(os.environ), args.environment)
    if args.github_mask:
        for command in github_mask_commands(values):
            print(command)
    write_tfvars(args.output, values)


if __name__ == "__main__":
    main()

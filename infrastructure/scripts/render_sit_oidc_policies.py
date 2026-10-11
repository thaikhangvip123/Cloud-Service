#!/usr/bin/env python3
"""Render SIT GitHub OIDC policy templates without committing account identifiers."""

import argparse
import getpass
import json
import os
import re
from pathlib import Path
from typing import Any


ACCOUNT_ID_PATTERN = re.compile(r"^[0-9]{12}$")
INSTANCE_ID_PATTERN = re.compile(r"^ssoins-[A-Za-z0-9-]+$")
IDENTITY_STORE_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{10,64}$")
ACCOUNT_ID_PLACEHOLDER = "__AWS_ACCOUNT_ID__"
INSTANCE_ID_PLACEHOLDER = "__SSO_INSTANCE_ID__"
IDENTITY_STORE_ID_PLACEHOLDER = "__IDENTITY_STORE_ID__"
TARGET_ACCOUNT_ARNS_PLACEHOLDER = "__TARGET_ACCOUNT_ARNS__"
POLICY_SIZE_LIMIT = 6144


def compact_policy_size(policy: dict[str, Any]) -> int:
    """Return the IAM policy character count with insignificant whitespace removed."""
    return len(json.dumps(policy, separators=(",", ":")))


def validate_inputs(
    account_id: str,
    instance_id: str,
    identity_store_id: str,
    target_account_ids: list[str],
) -> None:
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise ValueError("AWS account ID must contain exactly 12 ASCII digits")
    if not INSTANCE_ID_PATTERN.fullmatch(instance_id):
        raise ValueError("Identity Center instance ID must start with ssoins-")
    if not IDENTITY_STORE_ID_PATTERN.fullmatch(identity_store_id):
        raise ValueError("Identity Store ID has an invalid format")
    if not target_account_ids:
        raise ValueError("At least one target AWS account ID is required")
    if any(not ACCOUNT_ID_PATTERN.fullmatch(item) for item in target_account_ids):
        raise ValueError("Target AWS account IDs must contain exactly 12 ASCII digits")


def expand_target_accounts(value: Any, target_account_arns: list[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: expand_target_accounts(item, target_account_arns)
            for key, item in value.items()
        }
    if isinstance(value, list):
        expanded = []
        for item in value:
            if item == TARGET_ACCOUNT_ARNS_PLACEHOLDER:
                expanded.extend(target_account_arns)
            else:
                expanded.append(expand_target_accounts(item, target_account_arns))
        return expanded
    if value == TARGET_ACCOUNT_ARNS_PLACEHOLDER:
        return target_account_arns
    return value


def render_policy(
    template: Path,
    account_id: str,
    instance_id: str,
    identity_store_id: str,
    target_account_ids: list[str],
) -> dict[str, Any]:
    validate_inputs(account_id, instance_id, identity_store_id, target_account_ids)
    replacements = {
        ACCOUNT_ID_PLACEHOLDER: account_id,
        INSTANCE_ID_PLACEHOLDER: instance_id,
        IDENTITY_STORE_ID_PLACEHOLDER: identity_store_id,
    }
    rendered = template.read_text(encoding="utf-8")
    for placeholder, replacement in replacements.items():
        rendered = rendered.replace(placeholder, replacement)

    policy = expand_target_accounts(
        json.loads(rendered),
        [f"arn:aws:sso:::account/{item}" for item in dict.fromkeys(target_account_ids)],
    )
    unresolved = (
        ACCOUNT_ID_PLACEHOLDER,
        INSTANCE_ID_PLACEHOLDER,
        IDENTITY_STORE_ID_PLACEHOLDER,
        TARGET_ACCOUNT_ARNS_PLACEHOLDER,
    )
    serialized = json.dumps(policy)
    if any(placeholder in serialized for placeholder in unresolved):
        raise ValueError(f"Unresolved placeholder in {template.name}")
    if policy.get("Version") != "2012-10-17" or not policy.get("Statement"):
        raise ValueError(f"Invalid IAM policy structure in {template.name}")
    if compact_policy_size(policy) > POLICY_SIZE_LIMIT:
        raise ValueError(f"{template.name} exceeds the IAM managed policy size limit")
    return policy


def render_templates(
    template_dir: Path,
    output_dir: Path,
    account_id: str,
    instance_id: str,
    identity_store_id: str,
    target_account_ids: list[str],
) -> list[Path]:
    templates = sorted(template_dir.glob("*.template.json"))
    if not templates:
        raise ValueError(f"No policy templates found in {template_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for template in templates:
        output = output_dir / template.name.replace(".template", "")
        policy = render_policy(
            template,
            account_id,
            instance_id,
            identity_store_id,
            target_account_ids,
        )
        output.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
        if os.name != "nt":
            output.chmod(0o600)
        outputs.append(output)
    return outputs


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    template_dir = repository_root / "infrastructure" / "iam" / "github-actions"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=template_dir / "generated",
    )
    args = parser.parse_args()

    account_id = getpass.getpass("Deployment AWS account ID (input hidden): ").strip()
    instance_id = getpass.getpass(
        "IAM Identity Center instance ID, ssoins-... (input hidden): "
    ).strip()
    identity_store_id = getpass.getpass(
        "Identity Store ID (input hidden): "
    ).strip()
    target_input = getpass.getpass(
        "Target AWS account IDs, comma-separated; blank uses deployment account: "
    ).strip()
    target_account_ids = [
        item.strip() for item in target_input.split(",") if item.strip()
    ] or [account_id]

    outputs = render_templates(
        template_dir,
        args.output_dir,
        account_id,
        instance_id,
        identity_store_id,
        target_account_ids,
    )
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()

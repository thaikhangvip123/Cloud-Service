#!/usr/bin/env python3
"""Build and upload the access group mapping from Terraform outputs."""

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import boto3


def terraform_outputs(terraform_dir: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=terraform_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def value(outputs: dict[str, Any], name: str) -> Any:
    return outputs[name]["value"]


def build_mapping(outputs: dict[str, Any]) -> dict[str, Any]:
    groups = value(outputs, "access_groups")
    permission_sets = value(outputs, "permission_set_arns")
    accounts = value(outputs, "target_accounts")
    mapping: dict[str, Any] = {"access_groups": {}}
    for key, group in groups.items():
        account_key, access_type, tier = key.split("|")
        account_name = group.get("account_name", accounts[account_key]["account_name"])
        mapping["access_groups"][f"{account_name}-{access_type}-{tier}"] = {
            "group_id": group["group_id"],
            "group_name": group["group_name"],
            "account_name": account_name,
            "account_id": accounts[account_key]["account_id"],
            "access_type": access_type,
            "duration_tier": tier,
            "permission_set_arn": permission_sets[f"{access_type}|{tier}"],
        }
    return mapping


def validate_mapping(mapping: dict[str, Any]) -> None:
    required = {
        "group_id",
        "group_name",
        "account_name",
        "account_id",
        "access_type",
        "duration_tier",
        "permission_set_arn",
    }
    if not mapping.get("access_groups"):
        raise ValueError("Mapping contains no access groups")
    for key, item in mapping["access_groups"].items():
        missing = required - item.keys()
        if missing:
            raise ValueError(f"{key} is missing: {sorted(missing)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--terraform-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "terraform",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    outputs = terraform_outputs(args.terraform_dir)
    mapping = build_mapping(outputs)
    validate_mapping(mapping)
    if args.dry_run or args.validate:
        print(json.dumps(mapping, indent=2))
        return
    boto3.client("secretsmanager").put_secret_value(
        SecretId=value(outputs, "access_group_mapping_secret_name"),
        SecretString=json.dumps(mapping, separators=(",", ":")),
    )
    print(f"Updated {len(mapping['access_groups'])} access group mappings")


if __name__ == "__main__":
    main()

"""Regression checks for least-privilege Lambda IAM policies."""

import re
from pathlib import Path


LAMBDA_MODULE = (
    Path(__file__).parents[2] / "terraform" / "modules" / "lambda-functions" / "main.tf"
)


def test_only_approved_unscoped_resource_remains() -> None:
    source = LAMBDA_MODULE.read_text(encoding="utf-8")

    assert source.count('Resource = "*"') == 1
    assert re.search(
        r'Action\s*=\s*\["dynamodb:ListStreams"\]\s*Resource\s*=\s*"\*"',
        source,
    )
    assert 'var.environment == "sit" ? [' in source


def test_identity_store_permissions_use_scoped_arns() -> None:
    source = LAMBDA_MODULE.read_text(encoding="utf-8")

    assert "local.identity_store_arn" in source
    assert "local.identity_store_group_arns" in source
    assert "local.identity_store_all_groups_arn" in source
    assert "local.identity_store_all_users_arn" in source
    assert "local.identity_store_all_memberships_arn" in source
    assert '["identitystore:CreateGroupMembership"]' in source
    assert '["identitystore:DeleteGroupMembership"]' in source


def test_dynamodb_stream_expiry_is_blocked_outside_sit() -> None:
    source = LAMBDA_MODULE.read_text(encoding="utf-8")

    assert 'condition     = var.environment == "sit"' in source
    assert "Implement the precise scheduler design before deploying UAT or PROD." in source

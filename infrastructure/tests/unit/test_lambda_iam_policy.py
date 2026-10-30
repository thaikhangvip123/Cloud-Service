"""Regression checks for least-privilege Lambda IAM policies."""

import re
from pathlib import Path


LAMBDA_MODULE = Path(__file__).parents[2] / "terraform" / "modules" / "lambda-functions" / "main.tf"
API_MODULE = Path(__file__).parents[2] / "terraform" / "modules" / "api-gateway" / "main.tf"
ALARM_CONFIG = Path(__file__).parents[2] / "terraform" / "jit_access_additions.tf"
PERMISSION_SET_MODULE = (
    Path(__file__).parents[2]
    / "terraform"
    / "modules"
    / "identity-center-permission-sets"
    / "main.tf"
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


def test_dynamodb_stream_is_sit_only_and_scheduler_supports_all_environments() -> None:
    source = LAMBDA_MODULE.read_text(encoding="utf-8")

    assert 'count = var.environment == "sit" ? 1 : 0' in source
    assert 'resource "aws_scheduler_schedule_group" "expiry"' in source
    assert '"scheduler:CreateSchedule"' in source
    assert 'Principal = { Service = "scheduler.amazonaws.com" }' in source
    alarm_source = ALARM_CONFIG.read_text(encoding="utf-8")
    assert 'metric_name         = "InvocationDroppedCount"' in alarm_source


def test_api_gateway_access_logs_capture_auth_failures_without_payloads() -> None:
    source = API_MODULE.read_text(encoding="utf-8")

    assert 'resource "aws_api_gateway_account" "this"' in source
    assert "access_log_settings" in source
    assert 'errorMessage   = "$context.error.message"' in source
    assert "data_trace_enabled = false" in source
    assert "$context.requestBody" not in source


def test_permission_set_names_include_environment_prefix() -> None:
    source = PERMISSION_SET_MODULE.read_text(encoding="utf-8")

    expected = (
        'name             = "${var.resource_prefix}-'
        '${each.value.access_type}-${each.value.tier}"'
    )
    assert expected in source

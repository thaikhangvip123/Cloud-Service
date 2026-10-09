import json

import pytest

from scripts.render_ci_tfvars import build_tfvars, github_mask_commands, write_tfvars


def valid_environment():
    return {
        "CI_ADMIN_EMAIL": "admin@company.com",
        "CI_SES_SENDER_EMAIL": "jit-access@company.com",
        "CI_IDENTITY_CENTER_PORTAL_URL": "https://example.awsapps.com/start",
        "CI_APPROVAL_BASE_URL": "https://example.execute-api.amazonaws.com/action",
        "CI_JIRA_BASE_URL": "https://company.atlassian.net",
        "CI_JIRA_EMAIL": "jira-bot@company.com",
        "CI_JIRA_API_TOKEN": "placeholder-api-token",
        "CI_API_KEY_VALUE": "placeholder-api-key-value",
        "CI_WEBHOOK_HMAC_SECRET": "placeholder-webhook-hmac-secret",
        "CI_APPROVAL_TOKEN_SECRET": "placeholder-approval-token-secret",
        "CI_TARGET_ACCOUNTS_JSON": json.dumps(
            {
                "application": {
                    "account_id": "123456789012",
                    "account_name": "application",
                }
            }
        ),
    }


def test_build_tfvars_parses_target_accounts():
    values = build_tfvars(valid_environment(), "sit")

    assert values["target_accounts"]["application"]["account_id"] == "123456789012"
    assert values["jira_email"] == "jira-bot@company.com"
    assert values["environment"] == "sit"
    assert values["duration_tiers"] == ["1h", "2h", "4h"]
    assert values["enable_organization_trail"] is False


def test_build_tfvars_sets_production_controls():
    values = build_tfvars(valid_environment(), "prod")

    assert values["duration_tiers"] == ["1h", "2h", "4h", "8h", "12h"]
    assert values["enable_organization_trail"] is True


def test_build_tfvars_rejects_unknown_environment():
    with pytest.raises(ValueError, match="sit, uat, or prod"):
        build_tfvars(valid_environment(), "development")


def test_build_tfvars_rejects_missing_values():
    environment = valid_environment()
    environment.pop("CI_API_KEY_VALUE")

    with pytest.raises(ValueError, match="CI_API_KEY_VALUE"):
        build_tfvars(environment, "sit")


def test_build_tfvars_rejects_invalid_target_accounts_json():
    environment = valid_environment()
    environment["CI_TARGET_ACCOUNTS_JSON"] = "not-json"

    with pytest.raises(ValueError, match="valid JSON"):
        build_tfvars(environment, "sit")


def test_build_tfvars_rejects_account_id_command_injection():
    environment = valid_environment()
    environment["CI_TARGET_ACCOUNTS_JSON"] = json.dumps(
        {
            "application": {
                "account_id": "123456789012\n::add-mask::unexpected",
                "account_name": "application",
            }
        }
    )

    with pytest.raises(ValueError, match="12-digit account_id"):
        build_tfvars(environment, "sit")


def test_github_mask_commands_mask_individual_account_ids():
    commands = github_mask_commands(build_tfvars(valid_environment(), "sit"))

    assert commands == ["::add-mask::123456789012"]


def test_write_tfvars_does_not_pretty_print_secrets(tmp_path):
    output = tmp_path / "ci.tfvars.json"

    write_tfvars(output, build_tfvars(valid_environment(), "sit"))

    content = output.read_text(encoding="utf-8")
    assert "\n" not in content
    assert json.loads(content)["api_key_value"] == "placeholder-api-key-value"

from scripts.summarize_tfplan import summarize_plan


def test_summary_contains_addresses_and_counts_without_values():
    plan = {
        "resource_changes": [
            {
                "address": "module.api.aws_api_gateway_rest_api.this",
                "change": {
                    "actions": ["update"],
                    "before": {"secret": "before-secret"},
                    "after": {"secret": "after-secret"},
                },
            },
            {
                "address": 'module.groups.aws_identitystore_group.this["application"]',
                "change": {"actions": ["delete", "create"]},
            },
        ]
    }

    summary = summarize_plan(plan)

    assert "Update: 1" in summary
    assert "Replace: 1" in summary
    assert "module.api.aws_api_gateway_rest_api.this" in summary
    assert "before-secret" not in summary
    assert "after-secret" not in summary


def test_summary_removes_sensitive_instance_keys():
    plan = {
        "resource_changes": [
            {
                "address": (
                    'module.groups["example.module.123456789012"].'
                    'aws_identitystore_group.this["admin@company.com"]'
                ),
                "module_address": 'module.groups["example.module.123456789012"]',
                "type": "aws_identitystore_group",
                "name": "this",
                "change": {"actions": ["create"]},
            }
        ]
    }

    summary = summarize_plan(plan)

    assert "module.groups.aws_identitystore_group.this" in summary
    assert "123456789012" not in summary
    assert "admin@company.com" not in summary


def test_summary_reports_no_changes():
    plan = {
        "resource_changes": [
            {"address": "unchanged", "change": {"actions": ["no-op"]}},
            {"address": "data.lookup", "change": {"actions": ["read"]}},
        ]
    }

    assert "No infrastructure changes." in summarize_plan(plan)

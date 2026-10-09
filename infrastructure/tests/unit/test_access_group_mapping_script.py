from scripts.populate_access_group_mapping import build_mapping


def test_mapping_uses_account_name_instead_of_terraform_map_key():
    outputs = {
        "access_groups": {
            "value": {
                "sit-app|PowerUser|4h": {
                    "group_id": "group-1",
                    "group_name": "pa-sit-application-PowerUser-4h",
                    "account_name": "application",
                }
            }
        },
        "permission_set_arns": {"value": {"PowerUser|4h": "arn:permission-set"}},
        "target_accounts": {
            "value": {
                "sit-app": {
                    "account_id": "123456789012",
                    "account_name": "application",
                }
            }
        },
    }

    mapping = build_mapping(outputs)

    assert "application-PowerUser-4h" in mapping["access_groups"]
    assert "sit-app-PowerUser-4h" not in mapping["access_groups"]

import json
import hashlib
import hmac
import time
from unittest.mock import Mock

import pytest

from lambda_functions.executor.handler import (
    parse_request,
    process,
    process_emergency_revoke,
)
from shared.errors import (
    DurationExceededError,
    DynamoDBError,
    GroupMappingNotFoundError,
    UserNotFoundError,
)


def event(duration=3):
    body = {
        "requestId": "JIRA-1234",
        "requester": "user@company.com",
        "awsAccount": "application",
        "accessType": "PowerUser",
        "durationHours": duration,
    }
    raw = json.dumps(body, separators=(",", ":"))
    timestamp = str(int(time.time()))
    signature = hmac.new(b"unused", f"{timestamp}.{raw}".encode(), hashlib.sha256).hexdigest()
    return {
        "body": raw,
        "headers": {
            "x-api-key": "key",
            "x-request-timestamp": timestamp,
            "x-jira-signature": signature,
        },
        "requestContext": {"requestId": "correlation"},
    }


def dependencies():
    auth = {"api_key": "key", "hmac_secret": "unused"}
    manager = Mock()
    manager.map_duration_to_tier.return_value = "4h"
    manager.load_group_mapping.return_value = {"access_groups": {}}
    manager.find_access_group.return_value = {
        "group_id": "group",
        "group_name": "pa-sit-application-PowerUser-4h",
        "account_id": "123456789012",
        "account_name": "application",
        "permission_set_arn": "arn:permission-set",
    }
    manager.add_user_to_group.return_value = {"membership_id": "membership"}
    manager.build_session.return_value = {
        "sessionId": "membership-membership",
        "expires_at": "2026-06-12T12:00:00Z",
    }
    return auth, manager, Mock(), Mock(), Mock()


def test_valid_request_creates_membership_and_session():
    deps = dependencies()
    result = process(event(), deps)
    assert result["durationTier"] == "4h"
    deps[1].add_user_to_group.assert_called_once()
    deps[2].put_access_session.assert_called_once()


def test_session_failure_rolls_back_membership():
    deps = dependencies()
    deps[2].put_access_session.side_effect = RuntimeError("write failed")
    with pytest.raises(DynamoDBError):
        process(event(), deps)
    deps[1].remove_user_from_group.assert_called_once_with(
        "membership", "pa-sit-application-PowerUser-4h"
    )


def test_direct_emergency_revoke_returns_summary():
    deps = dependencies()
    deps[1].immediate_revoke_with_user_tag.return_value = {
        "user": "user@company.com",
        "revokedMemberships": 3,
        "status": "success",
    }

    result = process_emergency_revoke(
        {
            "operation": "emergency_revoke",
            "userEmail": "user@company.com",
            "correlationId": "correlation-1",
        },
        deps,
    )

    assert result["revokedMemberships"] == 3
    assert result["correlationId"] == "correlation-1"


def test_duration_over_twelve_hours_is_rejected():
    deps = dependencies()
    deps[1].map_duration_to_tier.side_effect = DurationExceededError(
        "durationHours cannot exceed 12 hours"
    )
    with pytest.raises(DurationExceededError):
        process(event(12.1), deps)


def test_missing_group_mapping_returns_specific_error():
    deps = dependencies()
    deps[1].find_access_group.side_effect = GroupMappingNotFoundError("No access group mapping")
    with pytest.raises(GroupMappingNotFoundError):
        process(event(), deps)


def test_missing_identity_center_user_returns_specific_error():
    deps = dependencies()
    deps[1].add_user_to_group.side_effect = UserNotFoundError("User not found")
    with pytest.raises(UserNotFoundError):
        process(event(), deps)


def test_nested_jira_payload_is_supported():
    request = parse_request(
        {
            "issue": {
                "key": "JIRA-2",
                "fields": {
                    "reporter": {"emailAddress": "user@example.com"},
                    "customfield_aws_account": {"value": "application"},
                    "customfield_access_type": {"value": "ReadOnly"},
                    "customfield_duration_hours": 1,
                },
            }
        }
    )

    assert request == {
        "requestId": "JIRA-2",
        "requester": "user@example.com",
        "awsAccount": "application",
        "accessType": "ReadOnly",
        "durationHours": 1,
    }

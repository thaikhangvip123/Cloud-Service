import pytest
from datetime import datetime

from shared.errors import DurationExceededError, ValidationError
from shared.jit_access import JITAccessManager, map_duration_to_tier


@pytest.mark.parametrize(
    ("hours", "tier"),
    [
        (0.1, "1h"),
        (1, "1h"),
        (1.1, "2h"),
        (3, "4h"),
        (7.5, "8h"),
        (10, "12h"),
        (12, "12h"),
    ],
)
def test_maps_duration_up_to_supported_tier(hours, tier):
    assert map_duration_to_tier(hours) == tier


@pytest.mark.parametrize("hours", [0, -1])
def test_rejects_non_positive_duration(hours):
    with pytest.raises(ValidationError):
        map_duration_to_tier(hours)


def test_rejects_duration_over_twelve_hours():
    with pytest.raises(DurationExceededError):
        map_duration_to_tier(12.1)


def test_session_expiry_uses_mapped_tier_not_requested_hours():
    manager = JITAccessManager(identity_center=None)
    session = manager.build_session(
        {
            "requestId": "JIRA-1",
            "requester": "user@example.com",
            "accessType": "PowerUser",
            "durationHours": 3,
            "durationTier": "4h",
            "correlationId": "correlation-1",
        },
        {
            "account_id": "123456789012",
            "account_name": "application",
            "group_id": "group-1",
            "group_name": "pa-sit-application-PowerUser-4h",
            "permission_set_arn": "arn:permission-set",
        },
        "membership-1",
    )
    granted = datetime.fromisoformat(session["granted_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
    assert (expires - granted).total_seconds() == 4 * 3600
    assert session["duration_hours"] == 3
    assert session["correlation_id"] == "correlation-1"

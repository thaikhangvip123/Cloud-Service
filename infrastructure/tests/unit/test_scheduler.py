from unittest.mock import Mock

from botocore.exceptions import ClientError

import pytest

from shared.errors import SchedulingError
from shared.scheduler import ExpiryScheduler


def session():
    return {
        "sessionId": "membership-example",
        "expires_at": "2026-10-29T08:30:00Z",
    }


def test_create_schedule_uses_exact_expiry_and_trusted_target():
    client = Mock()
    scheduler = ExpiryScheduler("pa-sit-expiry", "arn:role", "arn:lambda", client=client)

    name = scheduler.create(session())

    request = client.create_schedule.call_args.kwargs
    assert name.startswith("expiry-")
    assert request["ScheduleExpression"] == "at(2026-10-29T08:30:00)"
    assert request["ScheduleExpressionTimezone"] == "UTC"
    assert request["ActionAfterCompletion"] == "DELETE"
    assert request["Target"]["Arn"] == "arn:lambda"


def test_create_schedule_accepts_matching_existing_schedule():
    client = Mock()
    client.create_schedule.side_effect = ClientError(
        {"Error": {"Code": "ConflictException", "Message": "exists"}},
        "CreateSchedule",
    )
    scheduler = ExpiryScheduler("pa-sit-expiry", "arn:role", "arn:lambda", client=client)
    expected_input = '{"source":"jit.scheduler","sessionId":"membership-example"}'
    client.get_schedule.return_value = {
        "ScheduleExpression": "at(2026-10-29T08:30:00)",
        "ScheduleExpressionTimezone": "UTC",
        "Target": {
            "Arn": "arn:lambda",
            "RoleArn": "arn:role",
            "Input": expected_input,
        },
    }

    name = scheduler.create(session())

    assert name.startswith("expiry-")


def test_create_schedule_rejects_conflict_with_different_expiry():
    client = Mock()
    client.create_schedule.side_effect = ClientError(
        {"Error": {"Code": "ConflictException", "Message": "exists"}},
        "CreateSchedule",
    )
    client.get_schedule.return_value = {
        "ScheduleExpression": "at(2026-10-29T09:30:00)",
        "ScheduleExpressionTimezone": "UTC",
        "Target": {
            "Arn": "arn:lambda",
            "RoleArn": "arn:role",
            "Input": '{"source":"jit.scheduler","sessionId":"membership-example"}',
        },
    }
    scheduler = ExpiryScheduler("pa-sit-expiry", "arn:role", "arn:lambda", client=client)

    with pytest.raises(SchedulingError):
        scheduler.create(session())


def test_delete_schedule_ignores_not_found():
    client = Mock()
    client.delete_schedule.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "DeleteSchedule",
    )
    scheduler = ExpiryScheduler("pa-sit-expiry", "arn:role", "arn:lambda", client=client)

    scheduler.delete("expiry-example")

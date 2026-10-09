from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from shared.dynamodb_session import DynamoRepository
from shared.errors import TokenAlreadyUsedError


def test_mark_token_used_uses_condition():
    table = Mock()
    resource = Mock()
    resource.Table.return_value = table
    repository = DynamoRepository("sessions", "tokens", resource)
    repository.mark_token_used("token-1", "2026-01-01T00:00:00Z")
    kwargs = table.update_item.call_args.kwargs
    assert kwargs["ConditionExpression"] == "attribute_exists(token_id) AND used = :false"


def test_double_click_is_rejected():
    table = Mock()
    table.update_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "used"}}, "UpdateItem"
    )
    resource = Mock()
    resource.Table.return_value = table
    repository = DynamoRepository("sessions", "tokens", resource)
    with pytest.raises(TokenAlreadyUsedError):
        repository.mark_token_used("token-1", "2026-01-01T00:00:00Z")


def test_archive_session_removes_ttl_and_preserves_metadata():
    table = Mock()
    resource = Mock()
    resource.Table.return_value = table
    repository = DynamoRepository("sessions", "tokens", resource)

    repository.archive_access_session(
        {
            "sessionId": "membership-1",
            "requestId": "JIRA-1",
            "ttl": 100,
            "status": "Active",
        },
        "Expired",
        "2026-01-01T00:00:00Z",
    )

    item = table.put_item.call_args.kwargs["Item"]
    assert "ttl" not in item
    assert item["status"] == "Expired"
    assert item["expired_at"] == "2026-01-01T00:00:00Z"
    assert item["requestId"] == "JIRA-1"

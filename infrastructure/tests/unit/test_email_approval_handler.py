import hashlib
import hmac
import json
import time
from unittest.mock import Mock

import pytest

from lambda_functions.email_approval.handler import _create_tokens, _process_action, lambda_handler
from shared.approval_tokens import generate_token
from shared.errors import DurationExceededError, TokenAlreadyUsedError


def test_used_token_is_rejected():
    secret = "secret"
    token = generate_token(secret, int(time.time()) + 60, "token-1")
    repository = Mock()
    repository.get_approval_token.return_value = {
        "token_id": "token-1",
        "request_id": "JIRA-1",
        "action": "approve",
        "used": True,
    }

    with pytest.raises(TokenAlreadyUsedError):
        _process_action({"token": token, "action": "approve"}, secret, repository, Mock())


def test_valid_action_marks_token_used_before_jira_call():
    secret = "secret"
    token = generate_token(secret, int(time.time()) + 60, "token-1")
    repository = Mock()
    repository.get_approval_token.return_value = {
        "token_id": "token-1",
        "request_id": "JIRA-1",
        "action": "approve",
        "used": False,
    }
    jira = Mock()

    result = _process_action({"token": token, "action": "approve"}, secret, repository, jira)

    assert result["statusCode"] == 200
    repository.mark_token_used.assert_called_once()
    jira.approve_request.assert_called_once_with("JIRA-1")


def test_approval_request_rejects_duration_over_twelve_hours():
    with pytest.raises(DurationExceededError):
        _create_tokens(
            {
                "requestId": "JIRA-1",
                "requester": "user@example.com",
                "approverEmail": "approver@example.com",
                "awsAccount": "application",
                "accessType": "Admin",
                "durationHours": 12.1,
            },
            "secret",
            Mock(),
            Mock(),
        )


def approval_request_event(include_signature=True):
    body = json.dumps(
        {
            "requestId": "JIRA-1",
            "requester": "user@example.com",
            "approverEmail": "approver@example.com",
            "awsAccount": "application",
            "accessType": "ReadOnly",
            "durationHours": 1,
        },
        separators=(",", ":"),
    )
    timestamp = str(int(time.time()))
    headers = {"x-api-key": "key"}
    if include_signature:
        signature = hmac.new(
            b"hmac-secret",
            f"{timestamp}.{body}".encode(),
            hashlib.sha256,
        ).hexdigest()
        headers.update(
            {
                "x-request-timestamp": timestamp,
                "x-jira-signature": f"sha256={signature}",
            }
        )
    return {
        "httpMethod": "POST",
        "resource": "/email-approval/request",
        "headers": headers,
        "body": body,
    }


def test_email_approval_webhook_requires_valid_hmac():
    repository = Mock()
    dependencies = (
        {"api_key": "key", "hmac_secret": "hmac-secret"},
        "token-secret",
        repository,
        Mock(),
        Mock(),
    )

    result = lambda_handler(approval_request_event(False), None, dependencies=dependencies)

    assert result["statusCode"] == 401
    repository.put_approval_token.assert_not_called()


def test_email_approval_webhook_accepts_signed_payload():
    repository = Mock()
    dependencies = (
        {"api_key": "key", "hmac_secret": "hmac-secret"},
        "token-secret",
        repository,
        Mock(),
        Mock(),
    )

    result = lambda_handler(approval_request_event(), None, dependencies=dependencies)

    assert result["statusCode"] == 200
    assert repository.put_approval_token.call_count == 2

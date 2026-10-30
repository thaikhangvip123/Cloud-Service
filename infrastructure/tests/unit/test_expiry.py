from unittest.mock import Mock

import pytest

from lambda_functions.expiry.handler import lambda_handler, revoke
from shared.errors import IdentityCenterError, LegacySessionError


def stream_event(principal="dynamodb.amazonaws.com"):
    return {
        "Records": [
            {
                "eventID": "event-1",
                "eventName": "REMOVE",
                "userIdentity": {"principalId": principal},
                "dynamodb": {
                    "OldImage": {
                        "status": {"S": "Active"},
                        "membership_id": {"S": "membership-1"},
                        "requestId": {"S": "JIRA-1"},
                        "requester": {"S": "user@example.com"},
                        "group_name": {"S": "pa-sit-app-ReadOnly-1h"},
                    }
                },
            }
        ]
    }


def test_ttl_remove_revokes_membership():
    identity, repository, jira, notifier, sleeper = (
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )
    result = lambda_handler(
        stream_event(),
        None,
        dependencies=(identity, repository, jira, notifier, sleeper),
    )
    assert result["processed"] == 1
    identity.remove_membership.assert_called_once_with("membership-1")
    repository.archive_access_session.assert_called_once()


def test_manual_remove_is_ignored():
    identity, repository, jira, notifier, sleeper = (
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )
    result = lambda_handler(
        stream_event("user@example.com"),
        None,
        dependencies=(identity, repository, jira, notifier, sleeper),
    )
    assert result["processed"] == 0
    identity.remove_membership.assert_not_called()


def test_remove_without_ttl_service_identity_is_ignored():
    identity, repository, jira, notifier, sleeper = (Mock(), Mock(), Mock(), Mock(), Mock())
    event = stream_event()
    event["Records"][0].pop("userIdentity")

    result = lambda_handler(
        event,
        None,
        dependencies=(identity, repository, jira, notifier, sleeper),
    )

    assert result["processed"] == 0
    identity.remove_membership.assert_not_called()


def test_transient_identity_center_errors_are_retried():
    identity, repository, jira, notifier, sleeper = (
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
    )
    identity.remove_membership.side_effect = [
        IdentityCenterError("temporary"),
        None,
    ]

    result = lambda_handler(
        stream_event(),
        None,
        dependencies=(identity, repository, jira, notifier, sleeper),
    )

    assert result["processed"] == 1
    assert identity.remove_membership.call_count == 2
    sleeper.assert_called_once_with(1)


def test_retry_exhaustion_raises_and_does_not_archive_session():
    identity, repository, jira, notifier, sleeper = (Mock(), Mock(), Mock(), Mock(), Mock())
    identity.remove_membership.side_effect = IdentityCenterError("unavailable")
    session = {
        "membership_id": "membership-1",
        "requestId": "JIRA-1",
        "requester": "user@example.com",
    }

    with pytest.raises(IdentityCenterError):
        revoke(session, identity, repository, jira, notifier, sleeper)

    assert identity.remove_membership.call_count == 4
    assert [call.args[0] for call in sleeper.call_args_list] == [1, 2, 4]
    repository.archive_access_session.assert_not_called()


def test_legacy_session_uses_direct_assignment_revoke_path():
    identity, repository, jira, notifier, sleeper = (Mock(), Mock(), Mock(), Mock(), Mock())
    session = {
        "requestId": "JIRA-1",
        "requester": "user@example.com",
        "awsAccountId": "123456789012",
        "permission_set_arn": "arn:aws:sso:::permissionSet/example/legacy",
    }

    revoke(session, identity, repository, jira, notifier, sleeper)

    identity.remove_legacy_assignment.assert_called_once_with(
        "user@example.com",
        "123456789012",
        "arn:aws:sso:::permissionSet/example/legacy",
    )
    repository.archive_access_session.assert_called_once()


def test_legacy_session_missing_required_fields_fails_closed():
    identity, repository, jira, notifier, sleeper = (Mock(), Mock(), Mock(), Mock(), Mock())

    with pytest.raises(LegacySessionError):
        revoke(
            {"requestId": "JIRA-1", "requester": "user@example.com"},
            identity,
            repository,
            jira,
            notifier,
            sleeper,
        )

    identity.remove_legacy_assignment.assert_not_called()


def test_scheduler_event_loads_and_revokes_active_session():
    identity, repository, jira, notifier, sleeper = (Mock(), Mock(), Mock(), Mock(), Mock())
    repository.get_access_session.return_value = {
        "sessionId": "membership-1",
        "status": "Active",
        "membership_id": "membership-1",
        "requestId": "JIRA-1",
        "requester": "user@example.com",
    }

    result = lambda_handler(
        {"source": "jit.scheduler", "sessionId": "membership-1"},
        None,
        dependencies=(identity, repository, jira, notifier, sleeper),
    )

    assert result["processed"] == 1
    identity.remove_membership.assert_called_once_with("membership-1")


def test_scheduler_event_fails_when_session_was_removed():
    identity, repository, jira, notifier, sleeper = (Mock(), Mock(), Mock(), Mock(), Mock())
    repository.get_access_session.return_value = None

    with pytest.raises(IdentityCenterError):
        lambda_handler(
            {"source": "jit.scheduler", "sessionId": "membership-missing"},
            None,
            dependencies=(identity, repository, jira, notifier, sleeper),
        )


def test_scheduler_event_ignores_already_revoked_session():
    identity, repository, jira, notifier, sleeper = (Mock(), Mock(), Mock(), Mock(), Mock())
    repository.get_access_session.return_value = {
        "sessionId": "membership-1",
        "status": "Revoked",
    }

    result = lambda_handler(
        {"source": "jit.scheduler", "sessionId": "membership-1"},
        None,
        dependencies=(identity, repository, jira, notifier, sleeper),
    )

    assert result == {"status": "success", "processed": 0}
    identity.remove_membership.assert_not_called()

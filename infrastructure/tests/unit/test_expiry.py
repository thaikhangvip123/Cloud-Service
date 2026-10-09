from unittest.mock import Mock

from lambda_functions.expiry.handler import lambda_handler


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


def test_transient_identity_center_errors_are_retried():
    from shared.errors import IdentityCenterError

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

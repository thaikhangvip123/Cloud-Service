from unittest.mock import Mock

from shared.jira_client import JiraClient


def response(status=200, payload=None):
    item = Mock()
    item.status_code = status
    item.content = b"{}" if payload is not None else b""
    item.json.return_value = payload or {}
    item.raise_for_status.return_value = None
    return item


def credentials():
    return {
        "base_url": "https://example.atlassian.net",
        "email": "bot@example.com",
        "api_token": "token",
    }


def test_update_status_discovers_transition_by_destination_name():
    session = Mock()
    session.request.side_effect = [
        response(payload={"transitions": [{"id": "31", "to": {"name": "Expired"}}]}),
        response(status=204),
    ]
    client = JiraClient(credentials(), session=session, sleeper=Mock())

    client.update_request_status("JIRA-1", "Expired")

    assert session.request.call_args_list[1].kwargs["json"] == {"transition": {"id": "31"}}


def test_approval_uses_answerable_approval_id():
    session = Mock()
    session.request.side_effect = [
        response(
            payload={
                "values": [
                    {"id": "10", "canAnswerApproval": False},
                    {"id": "11", "canAnswerApproval": True},
                ]
            }
        ),
        response(payload={"id": "11", "finalDecision": "approved"}),
    ]
    client = JiraClient(credentials(), session=session, sleeper=Mock())

    client.approve_request("JIRA-1")

    assert (
        session.request.call_args_list[1]
        .args[1]
        .endswith("/rest/servicedeskapi/request/JIRA-1/approval/11")
    )


def test_retryable_jira_status_is_retried():
    session = Mock()
    session.request.side_effect = [
        response(status=503),
        response(payload={"ok": True}),
    ]
    sleeper = Mock()
    client = JiraClient(credentials(), session=session, sleeper=sleeper)

    assert client._request("GET", "/health") == {"ok": True}
    sleeper.assert_called_once_with(1)

from unittest.mock import Mock

from shared.jit_access import JITAccessManager


def test_emergency_revoke_removes_only_portal_groups():
    identity = Mock()
    repository = Mock()
    jira = Mock()
    identity.get_user_by_email.return_value = {"UserId": "user-1"}
    identity.memberships_for_user.return_value = [
        {"MembershipId": "membership-1", "GroupId": "group-1"},
        {"MembershipId": "membership-2", "GroupId": "group-2"},
    ]
    identity.describe_group.side_effect = [
        {"DisplayName": "pa-sit-app-Admin-1h"},
        {"DisplayName": "unrelated-group"},
    ]
    repository.get_access_session.return_value = {
        "sessionId": "membership-membership-1",
        "requestId": "JIRA-1",
        "ttl": 100,
        "status": "Active",
    }
    manager = JITAccessManager(
        identity,
        repository=repository,
        jira_client=jira,
        group_prefix="pa-",
    )

    result = manager.immediate_revoke_with_user_tag("user@example.com")

    assert result["revokedMemberships"] == 1
    identity.remove_membership.assert_called_once_with("membership-1")
    repository.archive_access_session.assert_called_once()
    jira.update_request_status.assert_called_once()

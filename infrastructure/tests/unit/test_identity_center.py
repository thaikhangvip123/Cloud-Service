from unittest.mock import Mock

import pytest

from botocore.exceptions import ClientError

from shared.errors import AmbiguousIdentityError
from shared.identity_center import IdentityCenterClient


def test_remove_membership_is_idempotent_when_already_deleted():
    client = Mock()
    client.delete_group_membership.side_effect = ClientError(
        {
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "already deleted",
            }
        },
        "DeleteGroupMembership",
    )
    identity = IdentityCenterClient("store-1", client=client)

    identity.remove_membership("membership-1")

    client.delete_group_membership.assert_called_once()


def test_conflict_returns_existing_membership_for_idempotent_retry():
    client = Mock()
    client.create_group_membership.side_effect = ClientError(
        {"Error": {"Code": "ConflictException", "Message": "already a member"}},
        "CreateGroupMembership",
    )
    identity = IdentityCenterClient("store-1", client=client)
    identity.memberships_for_user = Mock(
        return_value=[{"MembershipId": "membership-1", "GroupId": "group-1"}]
    )

    result = identity.add_user_to_group("user-1", "group-1")

    assert result == {"MembershipId": "membership-1", "AlreadyExists": True}


def test_ambiguous_email_lookup_fails_closed():
    identity = IdentityCenterClient("store-1", client=Mock())
    identity._pages = Mock(
        return_value=iter(
            [
                {"UserId": "user-1", "UserName": "user@example.com"},
                {"UserId": "user-2", "UserName": "user@example.com"},
            ]
        )
    )

    with pytest.raises(AmbiguousIdentityError):
        identity.get_user_by_email("user@example.com")


def test_legacy_assignment_waits_for_successful_deletion():
    identity_store = Mock()
    ssoadmin = Mock()
    identity = IdentityCenterClient(
        "store-1",
        client=identity_store,
        instance_arn="arn:aws:sso:::instance/example",
        ssoadmin_client=ssoadmin,
        sleeper=Mock(),
    )
    identity.get_user_by_email = Mock(return_value={"UserId": "user-1"})
    ssoadmin.delete_account_assignment.return_value = {
        "AccountAssignmentDeletionStatus": {"RequestId": "request-1"}
    }
    ssoadmin.describe_account_assignment_deletion_status.side_effect = [
        {"AccountAssignmentDeletionStatus": {"Status": "IN_PROGRESS"}},
        {"AccountAssignmentDeletionStatus": {"Status": "SUCCEEDED"}},
    ]

    identity.remove_legacy_assignment(
        "user@example.com",
        "123456789012",
        "arn:aws:sso:::permissionSet/example/legacy",
    )

    assert ssoadmin.describe_account_assignment_deletion_status.call_count == 2

from unittest.mock import Mock

from botocore.exceptions import ClientError

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

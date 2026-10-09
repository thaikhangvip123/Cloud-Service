"""IAM Identity Center Identity Store operations."""

from typing import Any, Iterator, cast

import boto3
from botocore.exceptions import ClientError

from shared.errors import IdentityCenterError, UserNotFoundError


class IdentityCenterClient:
    def __init__(self, identity_store_id: str, client=None):
        self.identity_store_id = identity_store_id
        self.client = client or boto3.client("identitystore")

    def _pages(self, operation: str, result_key: str, **kwargs: Any) -> Iterator[dict[str, Any]]:
        paginator = cast(Any, self.client).get_paginator(operation)
        for page in paginator.paginate(IdentityStoreId=self.identity_store_id, **kwargs):
            yield from page.get(result_key, [])

    def get_user_by_email(self, email: str) -> dict[str, Any]:
        users = list(
            self._pages(
                "list_users",
                "Users",
                Filters=[{"AttributePath": "UserName", "AttributeValue": email}],
            )
        )
        if not users:
            users = [
                user
                for user in self._pages("list_users", "Users")
                if any(
                    item.get("Value", "").lower() == email.lower()
                    for item in user.get("Emails", [])
                )
            ]
        if not users:
            raise UserNotFoundError(f"Identity Center user not found for {email}")
        return users[0]

    def add_user_to_group(self, user_id: str, group_id: str) -> dict[str, Any]:
        try:
            return dict(
                self.client.create_group_membership(
                    IdentityStoreId=self.identity_store_id,
                    GroupId=group_id,
                    MemberId={"UserId": user_id},
                )
            )
        except ClientError as exc:
            raise IdentityCenterError("Unable to create group membership") from exc

    def remove_membership(self, membership_id: str) -> None:
        try:
            self.client.delete_group_membership(
                IdentityStoreId=self.identity_store_id, MembershipId=membership_id
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in {"ResourceNotFoundException", "ResourceNotFound"}:
                raise IdentityCenterError("Unable to delete group membership") from exc

    def memberships_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return list(
            self._pages(
                "list_group_memberships_for_member",
                "GroupMemberships",
                MemberId={"UserId": user_id},
            )
        )

    def describe_group(self, group_id: str) -> dict[str, Any]:
        return dict(
            self.client.describe_group(IdentityStoreId=self.identity_store_id, GroupId=group_id)
        )

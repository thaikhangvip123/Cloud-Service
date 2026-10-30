"""IAM Identity Center Identity Store and legacy assignment operations."""

import time
from typing import Any, Iterator, cast

import boto3
from botocore.exceptions import ClientError

from shared.errors import AmbiguousIdentityError, IdentityCenterError, UserNotFoundError


class IdentityCenterClient:
    def __init__(
        self,
        identity_store_id: str,
        client=None,
        instance_arn: str = "",
        ssoadmin_client=None,
        sleeper=time.sleep,
    ):
        self.identity_store_id = identity_store_id
        self.client = client or boto3.client("identitystore")
        self.instance_arn = instance_arn
        self.ssoadmin = ssoadmin_client or (
            boto3.client("sso-admin") if instance_arn else None
        )
        self.sleeper = sleeper

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
        if len(users) != 1:
            raise AmbiguousIdentityError(
                f"Multiple Identity Center users matched the requested email {email}"
            )
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
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "ConflictException":
                memberships = [
                    membership
                    for membership in self.memberships_for_user(user_id)
                    if membership.get("GroupId") == group_id
                ]
                if len(memberships) == 1:
                    return {
                        "MembershipId": memberships[0]["MembershipId"],
                        "AlreadyExists": True,
                    }
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

    def remove_legacy_assignment(
        self, user_email: str, account_id: str, permission_set_arn: str
    ) -> None:
        if not self.instance_arn or self.ssoadmin is None:
            raise IdentityCenterError("Identity Center instance ARN is required for legacy revoke")
        user = self.get_user_by_email(user_email)
        try:
            result = self.ssoadmin.delete_account_assignment(
                InstanceArn=self.instance_arn,
                TargetId=account_id,
                TargetType="AWS_ACCOUNT",
                PermissionSetArn=permission_set_arn,
                PrincipalType="USER",
                PrincipalId=user["UserId"],
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"ResourceNotFoundException", "ResourceNotFound"}:
                return
            raise IdentityCenterError("Unable to delete legacy account assignment") from exc
        request_id = result.get("AccountAssignmentDeletionStatus", {}).get("RequestId")
        if not request_id:
            raise IdentityCenterError("Legacy assignment deletion returned no request ID")
        for delay in (0, 1, 2, 4):
            if delay:
                self.sleeper(delay)
            status_result = self.ssoadmin.describe_account_assignment_deletion_status(
                InstanceArn=self.instance_arn,
                AccountAssignmentDeletionRequestId=request_id,
            )
            status = status_result.get("AccountAssignmentDeletionStatus", {}).get("Status")
            if status == "SUCCEEDED":
                return
            if status == "FAILED":
                raise IdentityCenterError("Legacy account assignment deletion failed")
        raise IdentityCenterError("Legacy account assignment deletion did not complete in time")

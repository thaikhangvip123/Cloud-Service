"""Core group-based JIT access domain service."""

from datetime import timedelta
import logging
from typing import Any

from shared.account_mapping import find_access_group
from shared.errors import DurationExceededError, ValidationError
from shared.logging_config import log
from shared.utils import isoformat_z, utc_now


def map_duration_to_tier(hours: float) -> str:
    try:
        value = float(hours)
    except (TypeError, ValueError) as exc:
        raise ValidationError("durationHours must be a number") from exc
    if value <= 0:
        raise ValidationError("durationHours must be greater than zero")
    for limit in (1, 2, 4, 8, 12):
        if value <= limit:
            return f"{limit}h"
    raise DurationExceededError("durationHours cannot exceed 12 hours")


class JITAccessManager:
    def __init__(
        self,
        identity_center,
        repository=None,
        secret_loader=None,
        jira_client=None,
        logger: logging.Logger | None = None,
        group_prefix: str = "pa-",
    ):
        self.identity_center = identity_center
        self.repository = repository
        self.secret_loader = secret_loader
        self.jira_client = jira_client
        self.logger = logger
        self.group_prefix = group_prefix

    def get_user_info_by_email(self, email: str) -> dict[str, Any]:
        return self.identity_center.get_user_by_email(email)

    def add_user_to_group(self, user_email: str, group_id: str, group_name: str) -> dict[str, Any]:
        user = self.get_user_info_by_email(user_email)
        result = self.identity_center.add_user_to_group(user["UserId"], group_id)
        return {
            "membership_id": result["MembershipId"],
            "user_id": user["UserId"],
            "group_id": group_id,
            "group_name": group_name,
        }

    def remove_user_from_group(self, membership_id: str, group_name: str) -> None:
        self.identity_center.remove_membership(membership_id)
        if self.logger:
            log(
                self.logger,
                logging.INFO,
                "Removed Identity Center group membership",
                operation="revoke_access",
                group_name=group_name,
            )

    def load_group_mapping(self, secret_name: str) -> dict[str, Any]:
        return self.secret_loader(secret_name)

    def find_access_group(
        self, account: str, access_type: str, tier: str, mapping: dict[str, Any]
    ) -> dict[str, Any]:
        return find_access_group(account, access_type, tier, mapping)

    def map_duration_to_tier(self, hours: float) -> str:
        return map_duration_to_tier(hours)

    def build_session(
        self,
        request: dict[str, Any],
        group: dict[str, Any],
        membership_id: str,
    ) -> dict[str, Any]:
        granted = utc_now()
        tier_hours = float(str(request["durationTier"]).removesuffix("h"))
        expires = granted + timedelta(hours=tier_hours)
        return {
            "sessionId": f"membership-{membership_id}",
            "requestId": request["requestId"],
            "requester": request["requester"],
            "awsAccountId": group["account_id"],
            "account_name": group["account_name"],
            "access_type": request["accessType"],
            "duration_hours": float(request["durationHours"]),
            "duration_tier": request["durationTier"],
            "group_id": group["group_id"],
            "group_name": group["group_name"],
            "membership_id": membership_id,
            "permission_set_arn": group["permission_set_arn"],
            "granted_at": isoformat_z(granted),
            "expires_at": isoformat_z(expires),
            "ttl": int(expires.timestamp()),
            "status": "Active",
            "correlation_id": request.get("correlationId", ""),
        }

    def immediate_revoke_with_user_tag(self, user_email: str) -> dict[str, Any]:
        user = self.get_user_info_by_email(user_email)
        revoked = 0
        failures = 0
        revoked_sessions: list[tuple[str, dict[str, Any] | None]] = []
        for membership in self.identity_center.memberships_for_user(user["UserId"]):
            group = self.identity_center.describe_group(membership["GroupId"])
            if group.get("DisplayName", "").startswith(self.group_prefix):
                membership_id = membership["MembershipId"]
                session_id = f"membership-{membership_id}"
                session = (
                    self.repository.get_access_session(session_id) if self.repository else None
                )
                try:
                    self.remove_user_from_group(
                        membership_id,
                        group.get("DisplayName", membership["GroupId"]),
                    )
                    revoked += 1
                    revoked_sessions.append((membership_id, session))
                except Exception:
                    failures += 1
                    if self.logger:
                        log(
                            self.logger,
                            logging.ERROR,
                            "Emergency membership revocation failed",
                            operation="emergency_revoke",
                            group_name=group.get("DisplayName"),
                        )
        for membership_id, session in revoked_sessions:
            if session and self.repository:
                try:
                    revoked_at = isoformat_z(utc_now())
                    self.repository.archive_access_session(session, "Revoked", revoked_at)
                    if self.jira_client:
                        self.jira_client.update_request_status(
                            session["requestId"],
                            "Revoked",
                            f"Emergency revocation removed membership {membership_id}.",
                        )
                except Exception:
                    failures += 1
                    if self.logger:
                        log(
                            self.logger,
                            logging.ERROR,
                            "Emergency revocation audit update failed",
                            operation="emergency_revoke",
                            request_id=session.get("requestId"),
                        )
        return {
            "user": user_email,
            "revokedMemberships": revoked,
            "failures": failures,
            "status": "success" if failures == 0 else "partial",
        }

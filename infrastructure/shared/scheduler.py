"""Create deterministic one-time schedules for precise access expiry."""

from datetime import datetime
import hashlib
import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from shared.errors import SchedulingError


class ExpiryScheduler:
    def __init__(self, group_name: str, role_arn: str, target_arn: str, client=None):
        self.group_name = group_name
        self.role_arn = role_arn
        self.target_arn = target_arn
        self.client = client or boto3.client("scheduler")

    @staticmethod
    def _schedule_name(session_id: str) -> str:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]
        return f"expiry-{digest}"

    @staticmethod
    def _schedule_expression(expires_at: str) -> str:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return f"at({expires.strftime('%Y-%m-%dT%H:%M:%S')})"

    def create(self, session: dict[str, Any]) -> str:
        if not self.group_name or not self.role_arn or not self.target_arn:
            raise SchedulingError("Expiry scheduler configuration is incomplete")
        session_id = str(session["sessionId"])
        name = self._schedule_name(session_id)
        schedule_expression = self._schedule_expression(str(session["expires_at"]))
        target_input = json.dumps(
            {"source": "jit.scheduler", "sessionId": session_id}, separators=(",", ":")
        )
        try:
            self.client.create_schedule(
                Name=name,
                GroupName=self.group_name,
                ScheduleExpression=schedule_expression,
                ScheduleExpressionTimezone="UTC",
                FlexibleTimeWindow={"Mode": "OFF"},
                ActionAfterCompletion="DELETE",
                ClientToken=hashlib.sha256(
                    f"{session_id}:{session['expires_at']}".encode("utf-8")
                ).hexdigest(),
                Target={
                    "Arn": self.target_arn,
                    "RoleArn": self.role_arn,
                    "Input": target_input,
                    "RetryPolicy": {
                        "MaximumEventAgeInSeconds": 3600,
                        "MaximumRetryAttempts": 3,
                    },
                },
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "ConflictException":
                existing = self.client.get_schedule(Name=name, GroupName=self.group_name)
                target = existing.get("Target", {})
                if (
                    existing.get("ScheduleExpression") == schedule_expression
                    and existing.get("ScheduleExpressionTimezone") == "UTC"
                    and target.get("Arn") == self.target_arn
                    and target.get("RoleArn") == self.role_arn
                    and target.get("Input") == target_input
                ):
                    return name
            raise SchedulingError("Unable to create the access expiry schedule") from exc
        return name

    def delete(self, name: str) -> None:
        try:
            self.client.delete_schedule(Name=name, GroupName=self.group_name)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in {"ResourceNotFoundException", "ResourceNotFound"}:
                raise SchedulingError("Unable to delete the access expiry schedule") from exc

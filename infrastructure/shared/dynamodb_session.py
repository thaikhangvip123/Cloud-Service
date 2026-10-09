"""DynamoDB repositories for sessions and approval tokens."""

from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

from shared.errors import TokenAlreadyUsedError


def _normalize(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


class DynamoRepository:
    def __init__(self, sessions_table: str, tokens_table: str, resource=None):
        resource = resource or boto3.resource("dynamodb")
        self.sessions = resource.Table(sessions_table) if sessions_table else None
        self.tokens = resource.Table(tokens_table) if tokens_table else None

    def put_access_session(self, session: dict[str, Any]) -> None:
        self.sessions.put_item(Item=_normalize(session))

    def get_access_session(self, session_id: str) -> dict[str, Any] | None:
        return self.sessions.get_item(Key={"sessionId": session_id}).get("Item")

    def mark_session_status(self, session_id: str, status: str) -> None:
        self.sessions.update_item(
            Key={"sessionId": session_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status},
        )

    def archive_access_session(self, session: dict[str, Any], status: str, status_at: str) -> None:
        archived = dict(session)
        archived.pop("ttl", None)
        archived["status"] = status
        archived[f"{status.lower()}_at"] = status_at
        self.put_access_session(archived)

    def put_approval_token(self, token_record: dict[str, Any]) -> None:
        self.tokens.put_item(Item=_normalize(token_record))

    def get_approval_token(self, token_id: str) -> dict[str, Any] | None:
        return self.tokens.get_item(Key={"token_id": token_id}).get("Item")

    def mark_token_used(self, token_id: str, used_at: str) -> None:
        try:
            self.tokens.update_item(
                Key={"token_id": token_id},
                UpdateExpression="SET used = :true, used_at = :used_at",
                ConditionExpression="attribute_exists(token_id) AND used = :false",
                ExpressionAttributeValues={
                    ":true": True,
                    ":false": False,
                    ":used_at": used_at,
                },
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise TokenAlreadyUsedError("Approval token was already used") from exc
            raise


def _default_repository() -> DynamoRepository:
    from shared.config import settings

    return DynamoRepository(settings.access_sessions_table, settings.approval_tokens_table)


def put_access_session(session: dict[str, Any]) -> None:
    _default_repository().put_access_session(session)


def mark_session_status(session_id: str, status: str) -> None:
    _default_repository().mark_session_status(session_id, status)


def get_access_session(session_id: str) -> dict[str, Any] | None:
    return _default_repository().get_access_session(session_id)


def archive_access_session(session: dict[str, Any], status: str, status_at: str) -> None:
    _default_repository().archive_access_session(session, status, status_at)


def put_approval_token(token_record: dict[str, Any]) -> None:
    _default_repository().put_approval_token(token_record)


def get_approval_token(token_id: str) -> dict[str, Any] | None:
    return _default_repository().get_approval_token(token_id)


def mark_token_used(token_id: str, used_at: str) -> None:
    _default_repository().mark_token_used(token_id, used_at)

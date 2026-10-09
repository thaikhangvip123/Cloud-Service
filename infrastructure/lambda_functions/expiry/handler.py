"""Revoke expired sessions emitted by DynamoDB TTL."""

import logging
import time
import uuid
from typing import Any

from boto3.dynamodb.types import TypeDeserializer

from shared.config import settings
from shared.dynamodb_session import DynamoRepository
from shared.email_notification import EmailNotifier
from shared.errors import IdentityCenterError
from shared.identity_center import IdentityCenterClient
from shared.jira_client import JiraClient
from shared.logging_config import get_logger, log
from shared.secrets import get_secret
from shared.utils import isoformat_z, utc_now

LOGGER = get_logger(__name__)
DESERIALIZER = TypeDeserializer()
_CACHED_DEPENDENCIES = None


def _deserialize(image: dict[str, Any]) -> dict[str, Any]:
    return {key: DESERIALIZER.deserialize(value) for key, value in image.items()}


def _is_ttl_remove(record: dict[str, Any]) -> bool:
    if record.get("eventName") != "REMOVE":
        return False
    principal = record.get("userIdentity", {}).get("principalId")
    return principal in (None, "dynamodb.amazonaws.com")


def _dependencies():
    global _CACHED_DEPENDENCIES
    if _CACHED_DEPENDENCIES is not None:
        return _CACHED_DEPENDENCIES
    _CACHED_DEPENDENCIES = (
        IdentityCenterClient(settings.identity_store_id),
        DynamoRepository(settings.access_sessions_table, settings.approval_tokens_table),
        JiraClient(get_secret(settings.jira_credentials_secret)),
        EmailNotifier(settings.ses_sender_email),
        time.sleep,
    )
    return _CACHED_DEPENDENCIES


def revoke(
    session: dict[str, Any],
    identity,
    repository,
    jira,
    notifier,
    sleeper=time.sleep,
) -> None:
    membership_id = session.get("membership_id")
    if membership_id:
        last_error = None
        for attempt, delay in enumerate((0, 1, 2, 4), start=1):
            if delay:
                sleeper(delay)
            try:
                identity.remove_membership(membership_id)
                last_error = None
                break
            except IdentityCenterError as exc:
                last_error = exc
                log(
                    LOGGER,
                    logging.WARNING,
                    "Identity Center revocation attempt failed",
                    correlation_id=session.get("correlation_id"),
                    request_id=session.get("requestId"),
                    operation="expire_access",
                    attempt=attempt,
                )
        if last_error:
            raise last_error
    repository.archive_access_session(session, "Expired", isoformat_z(utc_now()))
    jira.update_request_status(
        session["requestId"],
        "Expired",
        f"Temporary production access in {session.get('group_name', 'access group')} expired.",
    )
    try:
        notifier.send_access_expired_email(session["requester"], session["requestId"])
    except Exception:
        log(
            LOGGER,
            logging.WARNING,
            "Expiry email failed after access revocation",
            correlation_id=session.get("correlation_id"),
            request_id=session["requestId"],
            operation="send_access_expired_email",
        )


def lambda_handler(event: dict[str, Any], _context: Any, dependencies=None) -> dict[str, Any]:
    identity, repository, jira, notifier, sleeper = dependencies or _dependencies()
    processed = 0
    for record in event.get("Records", []):
        if not _is_ttl_remove(record):
            continue
        session = _deserialize(record.get("dynamodb", {}).get("OldImage", {}))
        if session.get("status") not in (None, "Active"):
            continue
        correlation_id = session.get("correlation_id") or record.get("eventID") or str(uuid.uuid4())
        log(
            LOGGER,
            logging.INFO,
            "Revoking expired JIT access",
            correlation_id=correlation_id,
            request_id=session.get("requestId"),
            operation="expire_access",
        )
        try:
            revoke(session, identity, repository, jira, notifier, sleeper)
        except Exception:
            LOGGER.exception(
                "Expiry processing failed",
                extra={
                    "context": {
                        "correlation_id": correlation_id,
                        "request_id": session.get("requestId"),
                        "operation": "expire_access",
                    }
                },
            )
            raise
        processed += 1
    return {"status": "success", "processed": processed}

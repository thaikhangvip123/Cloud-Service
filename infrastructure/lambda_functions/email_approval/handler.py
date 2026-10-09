"""Create approval emails and process signed single-use actions."""

from datetime import timedelta
from html import escape
import json
import logging
import uuid
from typing import Any

from shared.approval_tokens import generate_token, verify_token
from shared.config import settings
from shared.dynamodb_session import DynamoRepository
from shared.email_notification import EmailNotifier
from shared.errors import PortalError, TokenValidationError, ValidationError
from shared.jira_client import JiraClient
from shared.jit_access import map_duration_to_tier
from shared.logging_config import get_logger, log
from shared.secrets import get_secret
from shared.utils import (
    isoformat_z,
    normalized_headers,
    parse_json_body,
    response,
    utc_now,
)
from shared.webhook_auth import EMAIL_APPROVAL_SCHEMA, validate_api_key, validate_payload

LOGGER = get_logger(__name__)
VALID_ACTIONS = {"approve", "decline"}
_CACHED_DEPENDENCIES = None


def _dependencies():
    global _CACHED_DEPENDENCIES
    if _CACHED_DEPENDENCIES is not None:
        return _CACHED_DEPENDENCIES
    auth = get_secret(settings.webhook_auth_secret)
    token_secret = get_secret(settings.token_secret_name)
    secret_value = token_secret["hmac_secret"] if isinstance(token_secret, dict) else token_secret
    _CACHED_DEPENDENCIES = (
        auth,
        secret_value,
        DynamoRepository(settings.access_sessions_table, settings.approval_tokens_table),
        JiraClient(get_secret(settings.jira_credentials_secret)),
        EmailNotifier(settings.ses_sender_email),
    )
    return _CACHED_DEPENDENCIES


def _create_tokens(payload, secret, repository, notifier):
    validate_payload(payload, EMAIL_APPROVAL_SCHEMA)
    map_duration_to_tier(payload["durationHours"])
    now = utc_now()
    expiry = now + timedelta(hours=settings.token_ttl_hours)
    tokens = {}
    for action in VALID_ACTIONS:
        token_id = str(uuid.uuid4())
        tokens[action] = generate_token(secret, int(expiry.timestamp()), token_id)
        repository.put_approval_token(
            {
                "token_id": token_id,
                "request_id": payload["requestId"],
                "action": action,
                "created_at": isoformat_z(now),
                "expires_at": isoformat_z(expiry),
                "used": False,
                "ttl": int(expiry.timestamp()),
            }
        )
    notifier.send_approval_email(
        payload["approverEmail"],
        payload["requestId"],
        settings.approval_base_url,
        tokens["approve"],
        tokens["decline"],
        payload,
    )
    return {"status": "success", "message": "Approval email sent"}


def _process_action(query, secret, repository, jira):
    token = query.get("token", "")
    action = query.get("action", "")
    if action not in VALID_ACTIONS:
        raise ValidationError("action must be approve or decline")
    token_id, _ = verify_token(token, secret)
    record = repository.get_approval_token(token_id)
    if not record or record.get("action") != action:
        raise TokenValidationError("Approval token does not match this action")
    if record.get("used"):
        from shared.errors import TokenAlreadyUsedError

        raise TokenAlreadyUsedError("Approval token was already used")
    repository.mark_token_used(token_id, isoformat_z(utc_now()))
    if action == "approve":
        jira.approve_request(record["request_id"])
    else:
        jira.decline_request(record["request_id"])
    label = "approved" if action == "approve" else "declined"
    html = (
        "<!doctype html><html><body><h1>Request "
        f"{escape(label)}</h1><p>{escape(record['request_id'])} was {escape(label)}."
        "</p></body></html>"
    )
    return response(200, html, "text/html; charset=utf-8")


def lambda_handler(event: dict[str, Any], _context: Any, dependencies=None):
    correlation_id = event.get("requestContext", {}).get("requestId") or str(uuid.uuid4())
    try:
        auth, secret, repository, jira, notifier = dependencies or _dependencies()
        method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get(
            "method"
        )
        path = event.get("resource") or event.get("rawPath", "")
        log(
            LOGGER,
            logging.INFO,
            "Processing email approval request",
            correlation_id=correlation_id,
            operation="email_approval",
            http_method=method,
            route=path,
        )
        if method == "POST" and path.endswith("/email-approval/request"):
            validate_api_key(normalized_headers(event), auth["api_key"])
            payload, _ = parse_json_body(event)
            return response(200, _create_tokens(payload, secret, repository, notifier))
        if method == "GET" and path.endswith("/email-approval/action"):
            return _process_action(
                event.get("queryStringParameters") or {}, secret, repository, jira
            )
        return response(404, {"status": "error", "message": "Route not found"})
    except (json.JSONDecodeError, ValidationError) as exc:
        error = exc if isinstance(exc, PortalError) else ValidationError("Invalid JSON body")
        return response(
            error.status_code,
            {"status": "error", "errorCode": error.code, "message": str(error)},
        )
    except PortalError as exc:
        log(
            LOGGER,
            logging.WARNING,
            "Email approval request rejected",
            correlation_id=correlation_id,
            operation="email_approval",
            error_code=exc.code,
        )
        return response(
            exc.status_code, {"status": "error", "errorCode": exc.code, "message": str(exc)}
        )
    except Exception:
        LOGGER.exception(
            "Unhandled email approval error",
            extra={
                "context": {
                    "correlation_id": correlation_id,
                    "operation": "email_approval",
                }
            },
        )
        return response(
            500,
            {"status": "error", "errorCode": "INTERNAL_ERROR", "message": "Request failed"},
        )

"""Provision approved Jira requests through Identity Center group membership."""

import json
import logging
import uuid
from typing import Any

from shared.config import settings
from shared.dynamodb_session import DynamoRepository
from shared.email_notification import EmailNotifier
from shared.errors import DynamoDBError, JiraUpdateError, PortalError, ValidationError
from shared.identity_center import IdentityCenterClient
from shared.jira_client import JiraClient
from shared.jit_access import JITAccessManager
from shared.logging_config import get_logger, log
from shared.secrets import get_secret
from shared.utils import normalized_headers, parse_json_body, response
from shared.webhook_auth import validate_api_key, validate_payload, verify_hmac, PROVISION_SCHEMA

LOGGER = get_logger(__name__)
_CACHED_DEPENDENCIES = None


def _field(fields: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = fields.get(name)
        if isinstance(value, dict):
            value = value.get("value") or value.get("emailAddress") or value.get("name")
        if value not in (None, ""):
            return value
    return None


def parse_request(payload: dict[str, Any]) -> dict[str, Any]:
    fields = payload.get("issue", {}).get("fields", {})
    request = {
        "requestId": payload.get("requestId")
        or payload.get("issue", {}).get("key")
        or _field(fields, "requestId"),
        "requester": payload.get("requester")
        or _field(fields, "requester", "reporter", "customfield_requester"),
        "awsAccount": payload.get("awsAccount")
        or _field(fields, "awsAccount", "customfield_aws_account"),
        "accessType": payload.get("accessType")
        or _field(fields, "accessType", "customfield_access_type"),
        "durationHours": (
            payload.get("durationHours")
            if payload.get("durationHours") is not None
            else _field(fields, "durationHours", "customfield_duration_hours")
        ),
    }
    validate_payload(request, PROVISION_SCHEMA)
    return request


def _dependencies():
    global _CACHED_DEPENDENCIES
    if _CACHED_DEPENDENCIES is not None:
        return _CACHED_DEPENDENCIES
    auth = get_secret(settings.webhook_auth_secret)
    identity = IdentityCenterClient(settings.identity_store_id)
    repository = DynamoRepository(settings.access_sessions_table, settings.approval_tokens_table)
    jira = JiraClient(get_secret(settings.jira_credentials_secret))
    manager = JITAccessManager(
        identity,
        repository,
        get_secret,
        jira,
        LOGGER,
        settings.access_group_prefix,
    )
    notifier = EmailNotifier(settings.ses_sender_email)
    _CACHED_DEPENDENCIES = auth, manager, repository, jira, notifier
    return _CACHED_DEPENDENCIES


def process(event: dict[str, Any], dependencies=None) -> dict[str, Any]:
    correlation_id = event.get("requestContext", {}).get("requestId") or str(uuid.uuid4())
    headers = normalized_headers(event)
    payload, raw_body = parse_json_body(event)
    auth, manager, repository, jira, notifier = dependencies or _dependencies()
    validate_api_key(headers, auth["api_key"])
    verify_hmac(
        raw_body,
        headers,
        auth["hmac_secret"],
        required=settings.require_hmac,
    )
    request = parse_request(payload)
    tier = manager.map_duration_to_tier(request["durationHours"])
    request["durationTier"] = tier
    request["correlationId"] = correlation_id
    mapping = manager.load_group_mapping(settings.access_group_mapping_secret)
    group = manager.find_access_group(request["awsAccount"], request["accessType"], tier, mapping)
    log(
        LOGGER,
        logging.INFO,
        "Processing JIT access request",
        correlation_id=correlation_id,
        request_id=request["requestId"],
        operation="provision_access",
        requester=request["requester"],
        aws_account=request["awsAccount"],
        access_type=request["accessType"],
        duration_hours=request["durationHours"],
        duration_tier=tier,
    )
    membership = manager.add_user_to_group(
        request["requester"], group["group_id"], group["group_name"]
    )
    try:
        session = manager.build_session(request, group, membership["membership_id"])
        repository.put_access_session(session)
    except Exception as exc:
        manager.remove_user_from_group(membership["membership_id"], group["group_name"])
        raise DynamoDBError("Unable to persist access session") from exc
    try:
        jira.update_request_status(
            request["requestId"],
            "Approved",
            f"Access provisioned in group {group['group_name']} until {session['expires_at']}.",
        )
    except Exception as exc:
        raise JiraUpdateError("Access was granted but Jira could not be updated") from exc
    result = {
        "status": "success",
        "requestId": request["requestId"],
        "requester": request["requester"],
        "account": request["awsAccount"],
        "accessType": request["accessType"],
        "durationTier": tier,
        "expiresAt": session["expires_at"],
        "identityCenterPortalUrl": settings.portal_url,
    }
    try:
        notifier.send_access_granted_email(request["requester"], result)
    except Exception:
        log(
            LOGGER,
            logging.WARNING,
            "Access granted but notification email failed",
            correlation_id=correlation_id,
            request_id=request["requestId"],
            operation="send_access_granted_email",
        )
    return result


def process_emergency_revoke(event: dict[str, Any], dependencies=None) -> dict[str, Any]:
    correlation_id = event.get("correlationId") or str(uuid.uuid4())
    user_email = event.get("userEmail")
    if not isinstance(user_email, str) or "@" not in user_email:
        raise ValidationError("userEmail must be a valid email address")
    _, manager, _, _, _ = dependencies or _dependencies()
    log(
        LOGGER,
        logging.WARNING,
        "Processing emergency access revocation",
        correlation_id=correlation_id,
        operation="emergency_revoke",
        requester=user_email,
    )
    result = manager.immediate_revoke_with_user_tag(user_email)
    result["correlationId"] = correlation_id
    return result


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    correlation_id = event.get("requestContext", {}).get("requestId") or str(uuid.uuid4())
    try:
        if event.get("operation") == "emergency_revoke":
            return process_emergency_revoke(event)
        return response(200, process(event))
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
            "Provisioning request rejected",
            correlation_id=correlation_id,
            operation="provision_access",
            error_code=exc.code,
        )
        return response(
            exc.status_code, {"status": "error", "errorCode": exc.code, "message": str(exc)}
        )
    except Exception:
        LOGGER.exception(
            "Unhandled provisioning error",
            extra={
                "context": {
                    "correlation_id": correlation_id,
                    "operation": "provision_access",
                }
            },
        )
        return response(
            500,
            {
                "status": "error",
                "errorCode": "INTERNAL_ERROR",
                "message": "Unable to process access request",
            },
        )

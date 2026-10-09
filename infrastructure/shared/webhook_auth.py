"""API key, HMAC, timestamp and JSON-schema validation."""

import hashlib
import hmac
import time
from typing import Any

from jsonschema import FormatChecker
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from shared.errors import AuthenticationError, ValidationError

PROVISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["requestId", "requester", "awsAccount", "accessType", "durationHours"],
    "properties": {
        "requestId": {"type": "string", "minLength": 1},
        "requester": {"type": "string", "format": "email", "minLength": 3},
        "awsAccount": {"type": "string", "minLength": 1},
        "accessType": {"enum": ["ReadOnly", "PowerUser", "Admin"]},
        "durationHours": {"type": "number"},
    },
}

EMAIL_APPROVAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "requestId",
        "requester",
        "approverEmail",
        "awsAccount",
        "accessType",
        "durationHours",
    ],
    "properties": {
        **PROVISION_SCHEMA["properties"],
        "approverEmail": {"type": "string", "format": "email", "minLength": 3},
    },
    "additionalProperties": True,
}


def validate_api_key(headers: dict[str, str], expected: str) -> None:
    provided = headers.get("x-api-key", "")
    if not expected or not hmac.compare_digest(provided, expected):
        raise AuthenticationError("Invalid API key")


def verify_hmac(
    body: str,
    headers: dict[str, str],
    secret: str,
    required: bool = True,
    max_age_seconds: int = 300,
) -> None:
    signature = headers.get("x-jira-signature", "")
    timestamp = headers.get("x-request-timestamp", "")
    if not signature:
        if required:
            raise AuthenticationError("Missing webhook signature")
        return
    try:
        request_time = int(timestamp)
    except ValueError as exc:
        raise AuthenticationError("Invalid request timestamp") from exc
    if abs(int(time.time()) - request_time) > max_age_seconds:
        raise AuthenticationError("Stale request timestamp")
    message = f"{timestamp}.{body}".encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    supplied = signature.removeprefix("sha256=")
    if not hmac.compare_digest(supplied, expected):
        raise AuthenticationError("Invalid webhook signature")


def validate_payload(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    try:
        validate(
            instance=payload,
            schema=schema,
            format_checker=FormatChecker(),
        )
    except JsonSchemaValidationError as exc:
        raise ValidationError(f"Invalid request payload: {exc.message}") from exc

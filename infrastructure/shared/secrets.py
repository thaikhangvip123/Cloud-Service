"""Secrets Manager access with a warm-start cache."""

import base64
import json
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 300
_KNOWN_ERRORS = {
    "ResourceNotFoundException",
    "AccessDeniedException",
    "InvalidRequestException",
    "InvalidParameterException",
}


def get_secret(name: str, client=None, cache_ttl: int = _CACHE_TTL_SECONDS) -> Any:
    now = time.monotonic()
    cached = _CACHE.get(name)
    if cached and now - cached[0] < cache_ttl:
        return cached[1]
    client = client or boto3.client("secretsmanager")
    try:
        result = client.get_secret_value(SecretId=name)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in _KNOWN_ERRORS:
            raise RuntimeError(f"Unable to load required secret {name}: {code}") from exc
        raise
    value = result.get("SecretString")
    if value is None:
        value = base64.b64decode(result["SecretBinary"]).decode("utf-8")
    try:
        value = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        pass
    _CACHE[name] = (now, value)
    return value


def clear_secret_cache() -> None:
    _CACHE.clear()

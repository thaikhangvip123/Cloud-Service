"""Small, deterministic runtime helpers."""

from datetime import datetime, timezone
import json
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_json_body(event: dict[str, Any]) -> tuple[dict[str, Any], str]:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode("utf-8")
    if isinstance(raw, dict):
        return raw, json.dumps(raw, separators=(",", ":"))
    return json.loads(raw), raw


def response(status_code: int, body: dict[str, Any] | str, content_type: str = "application/json"):
    payload = json.dumps(body) if isinstance(body, dict) else body
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": content_type,
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
        "body": payload,
    }


def normalized_headers(event: dict[str, Any]) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}

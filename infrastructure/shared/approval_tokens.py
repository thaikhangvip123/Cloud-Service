"""Signed, expiring, single-use approval token helpers."""

from datetime import datetime, timezone
import hashlib
import hmac
import uuid

from shared.errors import TokenValidationError


def generate_token(secret: str, expires_at: int, token_id: str | None = None) -> str:
    token_id = token_id or str(uuid.uuid4())
    payload = f"{token_id}.{expires_at}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str, secret: str, now: int | None = None) -> tuple[str, int]:
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenValidationError("Invalid approval token format")
    token_id, expiry_text, signature = parts
    try:
        expiry = int(expiry_text)
    except ValueError as exc:
        raise TokenValidationError("Invalid approval token expiry") from exc
    expected = hmac.new(
        secret.encode(), f"{token_id}.{expiry}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise TokenValidationError("Invalid approval token signature")
    current = now if now is not None else int(datetime.now(timezone.utc).timestamp())
    if expiry < current:
        raise TokenValidationError("Approval token has expired")
    return token_id, expiry

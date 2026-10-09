import hashlib
import hmac
import time

import pytest

from shared.errors import AuthenticationError
from shared.webhook_auth import validate_api_key, verify_hmac


def signed_headers(body, secret):
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256
    ).hexdigest()
    return {
        "x-request-timestamp": timestamp,
        "x-jira-signature": f"sha256={signature}",
    }


def test_valid_api_key_is_accepted():
    validate_api_key({"x-api-key": "correct"}, "correct")


def test_invalid_api_key_is_rejected():
    with pytest.raises(AuthenticationError):
        validate_api_key({"x-api-key": "wrong"}, "correct")


def test_valid_hmac_is_accepted():
    body = '{"requestId":"JIRA-1"}'
    verify_hmac(body, signed_headers(body, "secret"), "secret")


def test_tampered_body_is_rejected():
    headers = signed_headers("original", "secret")
    with pytest.raises(AuthenticationError):
        verify_hmac("tampered", headers, "secret")


def test_missing_signature_is_rejected_when_required():
    with pytest.raises(AuthenticationError):
        verify_hmac("body", {}, "secret", required=True)

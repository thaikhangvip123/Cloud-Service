import time

import pytest

from shared.approval_tokens import generate_token, verify_token
from shared.errors import TokenValidationError


def test_valid_token_is_accepted():
    expiry = int(time.time()) + 60
    token = generate_token("secret", expiry, "id")
    assert verify_token(token, "secret") == ("id", expiry)


def test_expired_token_is_rejected():
    token = generate_token("secret", 10, "id")
    with pytest.raises(TokenValidationError):
        verify_token(token, "secret", now=11)


def test_tampered_signature_is_rejected():
    token = generate_token("secret", int(time.time()) + 60, "id")
    replacement = "0" if token[-1] != "0" else "1"
    with pytest.raises(TokenValidationError):
        verify_token(token[:-1] + replacement, "secret")

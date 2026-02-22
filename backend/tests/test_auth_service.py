# tests for auth service — password hashing and jwt tokens
# unit tests for app/services/auth_service.py

import pytest
from datetime import timedelta

from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestPasswordHashing:
    """password hashing and verification"""

    def test_hash_password_returns_string(self):
        hashed = hash_password("test_password")
        assert isinstance(hashed, str)
        assert hashed != "test_password"

    def test_hash_password_different_each_time(self):
        """bcrypt salts should make each hash unique"""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2

    def test_verify_password_correct(self):
        hashed = hash_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False


class TestJWTTokens:
    """jwt token creation and validation"""

    def test_create_access_token(self):
        token = create_access_token({"sub": "user123", "role": "therapist"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        token = create_access_token({"sub": "user123", "role": "therapist"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["role"] == "therapist"
        assert payload["type"] == "access"

    def test_access_token_has_expiry(self):
        token = create_access_token({"sub": "user123"})
        payload = decode_token(token)
        assert "exp" in payload

    def test_create_refresh_token(self):
        token = create_refresh_token({"sub": "user123", "role": "patient"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user123"

    def test_decode_invalid_token(self):
        result = decode_token("invalid.token.here")
        assert result is None

    def test_decode_empty_token(self):
        result = decode_token("")
        assert result is None

    def test_token_preserves_custom_claims(self):
        token = create_access_token({"sub": "u1", "role": "therapist", "custom": "value"})
        payload = decode_token(token)
        assert payload["custom"] == "value"

    def test_custom_expiry(self):
        token = create_access_token(
            {"sub": "user1"},
            expires_delta=timedelta(minutes=5),
        )
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user1"

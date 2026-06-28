from datetime import timedelta

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)


class TestAccessToken:
    def test_contains_correct_claims(self):
        token = create_access_token({"sub": "user-123", "tenant_id": "tenant-456"})
        payload = verify_token(token)
        assert payload["sub"] == "user-123"
        assert payload["tenant_id"] == "tenant-456"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_expired_token_raises_token_error(self):
        token = create_access_token({"sub": "x"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(TokenError):
            verify_token(token)

    def test_invalid_signature_raises_token_error(self):
        token = create_access_token({"sub": "x"})
        parts = token.split(".")
        parts[2] = "invalidsignature"
        with pytest.raises(TokenError):
            verify_token(".".join(parts))


class TestRefreshToken:
    def test_contains_refresh_type(self):
        token = create_refresh_token({"sub": "user-123", "tenant_id": "t-1"})
        payload = verify_token(token)
        assert payload["type"] == "refresh"

    def test_expired_refresh_raises_token_error(self):
        from datetime import timedelta
        from unittest.mock import patch

        with patch("app.core.security.timedelta", return_value=timedelta(seconds=-1)):
            token = create_refresh_token({"sub": "x", "tenant_id": "t"})
        with pytest.raises(TokenError):
            verify_token(token)


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("minha_senha")
        assert hashed != "minha_senha"

    def test_verify_correct_password(self):
        hashed = hash_password("minha_senha")
        assert verify_password("minha_senha", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("minha_senha")
        assert verify_password("senha_errada", hashed) is False

    def test_two_hashes_of_same_password_differ(self):
        # bcrypt gera salt aleatório
        h1 = hash_password("abc123")
        h2 = hash_password("abc123")
        assert h1 != h2
        assert verify_password("abc123", h1) is True
        assert verify_password("abc123", h2) is True

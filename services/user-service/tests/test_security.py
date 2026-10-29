import jwt
import pytest

from app.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong-password", h)


def test_token_roundtrip():
    assert decode_token(create_token("user-1")) == "user-1"


def test_tampered_token_rejected():
    token = create_token("user-1")
    with pytest.raises(jwt.PyJWTError):
        decode_token(token[:-2] + "xx")

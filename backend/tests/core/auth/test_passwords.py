"""Tests for local account password hashing helpers."""

from __future__ import annotations

from src.core.auth.passwords import hash_password, verify_password


def test_password_hash_verifies_original_password() -> None:
    """A stored password hash verifies the original password only."""
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", password_hash) is True
    assert verify_password("wrong password", password_hash) is False


def test_password_hash_uses_unique_salt() -> None:
    """Hashing the same password twice should produce different stored hashes."""
    first = hash_password("same-password")
    second = hash_password("same-password")

    assert first != second

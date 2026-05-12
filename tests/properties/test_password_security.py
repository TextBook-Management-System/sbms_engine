# Feature: sbms-api-endpoints, Property 9: Password Security Round-Trip
"""
Property-based tests for password security round-trip.

Tests validate that:
1. For any valid password (≥ 8 characters), _hash_password produces a valid
   bcrypt hash (starts with $2b$)
2. _verify_password returns True for the original password against its hash
3. _verify_password returns False for any different password against the hash
4. The hash is different from the original password

**Validates: Requirements 5.1, 5.6**
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.auth_service import _hash_password, _verify_password


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: generate valid passwords (≥ 8 characters)
# Use ASCII printable characters common in passwords to keep bcrypt fast
valid_password_chars = st.characters(
    whitelist_categories=("L", "N", "P"),
    min_codepoint=32,
    max_codepoint=126,
)

valid_passwords = st.text(
    alphabet=valid_password_chars,
    min_size=8,
    max_size=50,  # Keep shorter to avoid bcrypt's 72-byte limit edge cases
)

# Strategy: generate a pair of different passwords
different_passwords = st.tuples(valid_passwords, valid_passwords).filter(
    lambda pair: pair[0] != pair[1]
)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestPasswordSecurityRoundTrip:
    """
    Property 9: Password Security Round-Trip

    For any valid password (≥ 8 characters), after registration the stored
    password_hash SHALL be a valid bcrypt hash that verifies against the
    original password, AND the password or hash SHALL never appear in any
    API response body.
    """

    @given(password=valid_passwords)
    @settings(max_examples=50, deadline=None)
    def test_hash_produces_valid_bcrypt_format(self, password: str):
        """For any password ≥ 8 chars, _hash_password produces a valid bcrypt hash (starts with $2b$)."""
        hashed = _hash_password(password)

        # bcrypt hashes always start with $2b$ (the version identifier)
        assert hashed.startswith("$2b$"), (
            f"Expected bcrypt hash starting with '$2b$', got: {hashed[:10]}..."
        )

        # bcrypt hashes are always 60 characters long
        assert len(hashed) == 60, (
            f"Expected bcrypt hash of length 60, got length {len(hashed)}"
        )

    @given(password=valid_passwords)
    @settings(max_examples=50, deadline=None)
    def test_verify_returns_true_for_original_password(self, password: str):
        """_verify_password returns True for the original password against its hash."""
        hashed = _hash_password(password)

        assert _verify_password(password, hashed) is True, (
            f"_verify_password should return True for the original password"
        )

    @given(data=different_passwords)
    @settings(max_examples=50, deadline=None)
    def test_verify_returns_false_for_different_password(self, data: tuple):
        """_verify_password returns False for any different password against the hash."""
        original_password, different_password = data

        hashed = _hash_password(original_password)

        assert _verify_password(different_password, hashed) is False, (
            f"_verify_password should return False for a different password"
        )

    @given(password=valid_passwords)
    @settings(max_examples=50, deadline=None)
    def test_hash_is_different_from_original_password(self, password: str):
        """The hash is different from the original password."""
        hashed = _hash_password(password)

        assert hashed != password, (
            "The hash must be different from the original password"
        )

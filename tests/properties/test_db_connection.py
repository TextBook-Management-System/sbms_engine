# Feature: sbms-api-endpoints, Property 3: Foreign Key Validation
"""
Property-based tests for database connection validation logic.

Tests validate that the _validate_database_url function in app/database/session.py
correctly rejects invalid DATABASE_URL values and that _build_engine applies
the correct connect_args based on the URL scheme.

**Validates: Requirements 1.4, 1.5, 1.6**
"""
import os
from unittest.mock import patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Strategies for generating invalid URL patterns
# ---------------------------------------------------------------------------

# Strategy: empty or whitespace-only strings (simulates missing DATABASE_URL)
empty_or_whitespace = st.one_of(
    st.just(""),
    st.text(alphabet=" \t\n\r", min_size=1, max_size=10),
)

# Strategy: malformed URLs that lack a valid host for non-sqlite schemes
malformed_mysql_urls = st.one_of(
    # Missing host entirely
    st.just("mysql+pymysql://"),
    st.just("mysql+pymysql:///dbname"),
    st.just("mysql://"),
    st.just("mysql:///dbname"),
    # Scheme present but no host after ://
    st.builds(
        lambda user, db: f"mysql+pymysql://{user}@/{db}",
        user=st.from_regex(r"[a-z]{1,8}", fullmatch=True),
        db=st.from_regex(r"[a-z]{1,8}", fullmatch=True),
    ),
)

# Strategy: valid MySQL URLs (for connect_args testing)
valid_mysql_urls = st.builds(
    lambda user, pw, host, port, db: f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}",
    user=st.from_regex(r"[a-z]{1,8}", fullmatch=True),
    pw=st.from_regex(r"[a-z0-9]{1,8}", fullmatch=True),
    host=st.from_regex(r"[a-z]{1,8}", fullmatch=True),
    port=st.integers(min_value=1, max_value=65535),
    db=st.from_regex(r"[a-z]{1,8}", fullmatch=True),
)

# Strategy: valid SQLite URLs
valid_sqlite_urls = st.one_of(
    st.just("sqlite:///test.db"),
    st.just("sqlite:///./data.db"),
    st.just("sqlite:///:memory:"),
    st.builds(
        lambda name: f"sqlite:///{name}.db",
        name=st.from_regex(r"[a-z]{1,10}", fullmatch=True),
    ),
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEmptyMissingDatabaseUrl:
    """Requirement 1.6: Missing/empty DATABASE_URL raises RuntimeError."""

    @given(url=empty_or_whitespace)
    @settings(max_examples=100, deadline=None)
    def test_empty_or_whitespace_url_raises_runtime_error(self, url: str):
        """Empty or whitespace-only DATABASE_URL must raise RuntimeError."""
        from app.database.session import _validate_database_url

        with pytest.raises(RuntimeError, match="(?i)missing"):
            _validate_database_url(url.strip())


class TestMalformedUrlRaisesError:
    """Requirement 1.4: Malformed URLs raise RuntimeError with host/port/failure info."""

    @given(url=malformed_mysql_urls)
    @settings(max_examples=100, deadline=None)
    def test_malformed_mysql_url_raises_runtime_error(self, url: str):
        """Malformed MySQL URLs must raise RuntimeError with diagnostic info."""
        from app.database.session import _validate_database_url

        with pytest.raises(RuntimeError) as exc_info:
            _validate_database_url(url)

        error_msg = str(exc_info.value)
        # Error message should contain host/port/failure information
        assert "host" in error_msg.lower() or "malformed" in error_msg.lower() or "missing" in error_msg.lower(), (
            f"Error message should include host/port/failure info, got: {error_msg}"
        )


class TestMysqlOmitsCheckSameThread:
    """Requirement 1.5: MySQL URLs do NOT include check_same_thread in connect args."""

    @given(url=valid_mysql_urls)
    @settings(max_examples=100, deadline=None)
    def test_mysql_url_does_not_use_check_same_thread(self, url: str):
        """For MySQL URLs, check_same_thread must NOT be in connect_args."""
        from app.database.session import _build_engine
        from unittest.mock import patch, MagicMock

        mock_engine = MagicMock()
        with patch("app.database.session.create_engine", return_value=mock_engine) as mock_create:
            _build_engine(url)

            # Verify create_engine was called
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            connect_args = call_kwargs.kwargs.get("connect_args", call_kwargs[1].get("connect_args", {}))

            assert "check_same_thread" not in connect_args, (
                f"MySQL URL should not have check_same_thread in connect_args, "
                f"but got connect_args={connect_args}"
            )


class TestSqliteIncludesCheckSameThread:
    """Requirement 1.5 (inverse): SQLite URLs DO include check_same_thread=False."""

    @given(url=valid_sqlite_urls)
    @settings(max_examples=100, deadline=None)
    def test_sqlite_url_includes_check_same_thread_false(self, url: str):
        """For SQLite URLs, check_same_thread=False must be in connect_args."""
        from app.database.session import _build_engine
        from unittest.mock import patch, MagicMock

        mock_engine = MagicMock()
        with patch("app.database.session.create_engine", return_value=mock_engine) as mock_create:
            _build_engine(url)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            connect_args = call_kwargs.kwargs.get("connect_args", call_kwargs[1].get("connect_args", {}))

            assert connect_args.get("check_same_thread") is False, (
                f"SQLite URL should have check_same_thread=False in connect_args, "
                f"but got connect_args={connect_args}"
            )

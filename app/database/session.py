import os
import logging
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def _validate_database_url(database_url: str) -> None:
    """Validate that DATABASE_URL is present and well-formed.

    Raises RuntimeError with host/port/failure details when the URL is
    missing or malformed.
    """
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is missing. "
            "Please set it to a valid SQLAlchemy database URL "
            "(e.g. mysql+pymysql://user:pass@host:3306/dbname)."
        )

    try:
        parsed = urlparse(database_url)
        scheme = parsed.scheme  # e.g. "mysql+pymysql" or "sqlite"

        # For non-sqlite URLs, ensure host is present
        if not scheme.startswith("sqlite"):
            if not parsed.hostname:
                raise ValueError("host is missing from the URL")
            # Port is optional (defaults vary by driver), but we include it in
            # error messages when available.
    except Exception as exc:
        host = getattr(urlparse(database_url), "hostname", "unknown") or "unknown"
        port = getattr(urlparse(database_url), "port", "unknown") or "unknown"
        raise RuntimeError(
            f"DATABASE_URL is malformed. host={host}, port={port}, "
            f"failure=parsing error ({exc}). "
            "Expected format: mysql+pymysql://user:pass@host:port/dbname"
        ) from exc


def _build_engine(database_url: str):
    """Create the SQLAlchemy engine with appropriate configuration.

    For MySQL URLs (starting with 'mysql'), connection pooling parameters are
    read from environment variables:
      - DB_POOL_SIZE (default: 5)
      - DB_MAX_OVERFLOW (default: 10)
      - DB_POOL_TIMEOUT (default: 30)

    For SQLite URLs, the `check_same_thread` connect arg is applied.
    """
    _validate_database_url(database_url)

    connect_args: dict = {}
    engine_kwargs: dict = {}

    if database_url.startswith("mysql"):
        # MySQL with pymysql — configure connection pooling
        pool_size = int(os.environ.get("DB_POOL_SIZE", "5"))
        max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
        pool_timeout = int(os.environ.get("DB_POOL_TIMEOUT", "30"))

        engine_kwargs.update(
            {
                "pool_size": pool_size,
                "max_overflow": max_overflow,
                "pool_timeout": pool_timeout,
                "pool_pre_ping": True,
                "pool_recycle": 300,
            }
        )
        logger.info(
            "Configuring MySQL engine with pool_size=%d, max_overflow=%d, pool_timeout=%d",
            pool_size,
            max_overflow,
            pool_timeout,
        )
    elif database_url.startswith("sqlite"):
        # SQLite needs check_same_thread=False for FastAPI's async usage
        connect_args["check_same_thread"] = False

    try:
        engine = create_engine(
            database_url,
            connect_args=connect_args,
            **engine_kwargs,
        )
    except Exception as exc:
        parsed = urlparse(database_url)
        host = parsed.hostname or "unknown"
        port = parsed.port or "unknown"
        raise RuntimeError(
            f"Failed to create database engine. host={host}, port={port}, "
            f"failure={type(exc).__name__}: {exc}"
        ) from exc

    return engine


# Read DATABASE_URL from environment (via settings or directly)
# We import settings to stay consistent with the rest of the app, but
# validation uses the raw value.
from app.config.settings import settings  # noqa: E402

engine = _build_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

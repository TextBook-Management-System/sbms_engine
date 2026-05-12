"""Alembic environment configuration.

Reads DATABASE_URL from the application settings (which loads from .env)
and configures Alembic to use the project's SQLAlchemy models for
autogenerate support.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ensure the project root is on sys.path so app imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import settings  # noqa: E402
from app.database.session import Base  # noqa: E402
from app.models.database import (  # noqa: E402, F401 — import all models so metadata is populated
    GradeLevel,
    Subject,
    Department,
    School,
    User,
    UserRole,
    Grade,
    Learner,
    ParentLearner,
    Book,
    SchoolBooksInventory,
    BookRequest,
    Delivery,
    BookBox,
    BookCopy,
    AIModelVersion,
    BookConditionScan,
    BookAllocation,
    ParentAcknowledgement,
    DamageNotification,
    ReplacementRequest,
    Escalation,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with the value from application settings
# Use set_main_option with %% escaping to avoid configparser interpolation issues
if settings.DATABASE_URL:
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The target metadata for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

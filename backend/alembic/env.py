"""
Alembic environment script.

Wired to the application's own `Settings` (so migrations always target the
same database the app would connect to) and to `Base.metadata` (so
`alembic revision --autogenerate` can diff the ORM models against the
database automatically instead of migrations being written by hand from
scratch).
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.db.session import Base  # noqa: E402
import app.models  # noqa: E402  (registers all models on Base.metadata)

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_uri)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Prevents Alembic from generating spurious diffs for the
            # PostGIS "spatial_ref_sys" reference table.
            include_object=lambda obj, name, type_, reflected, compare_to: not (
                type_ == "table" and name == "spatial_ref_sys"
            ),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

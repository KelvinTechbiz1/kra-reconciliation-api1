from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.database.database import engine

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    # disable_existing_loggers defaults to True, which silences every logger already
    # configured by the caller. app.init_db runs migrations before it seeds, so its own
    # startup output (seeded credentials, KRA sections) vanished from container logs.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Discover models via the central import module
import app.database.models  # noqa: F401

from app.database.base import Base  # noqa: E402

target_metadata = Base.metadata

# URL for offline mode (no DB connection needed)
settings = get_settings()
database_url = settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

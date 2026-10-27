import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context

# Add project root to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
project_root = os.path.abspath(os.path.join(backend_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.core.config import settings
from backend.app.db.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

def get_url():
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite")
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Allow override from connection passed directly in context
    connection = config.attributes.get("connection", None)

    if connection is not None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite"
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        url = get_url()
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        connectable = create_engine(url, connect_args=connect_args, poolclass=pool.NullPool)

        with connectable.connect() as conn:
            context.configure(
                connection=conn,
                target_metadata=target_metadata,
                render_as_batch=conn.dialect.name == "sqlite"
            )

            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

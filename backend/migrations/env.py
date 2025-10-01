from logging.config import fileConfig

from dotenv import load_dotenv

load_dotenv()
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio

from app.core.config import settings
from app.core.models import Base, RefreshToken, Study, User

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata
print("Alembic sees tables:", target_metadata.tables.keys())


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.
def get_database_url():
    return settings.db.url


def run_migrations_offline():
    """Оффлайн режим — без подключения к БД"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Выполняет миграции, используя подключение"""
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """Онлайн режим — подключение к БД через async engine"""
    connectable = async_engine_from_config(
        {
            **config.get_section(config.config_ini_section),
            "sqlalchemy.url": get_database_url(),
        },
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())

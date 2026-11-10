"""Настройка Alembic для автоматического управления схемой PostgreSQL."""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL

from alembic import context
from weather_analytics.config import get_settings
from weather_analytics.db.models import Base

# Конфигурация Alembic из alembic.ini.
config = context.config

# Сохраняем существующие логгеры приложения при запуске миграций.
if config.config_file_name is not None:
    fileConfig(
        config.config_file_name,
        disable_existing_loggers=False,
    )

# Метаданные SQLAlchemy используются командой revision --autogenerate.
target_metadata = Base.metadata


def get_database_url() -> URL:
    """Формирует подключение PostgreSQL из настроек приложения."""
    settings = get_settings()

    return URL.create(
        drivername='postgresql+psycopg',
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


def include_object(
    object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to,
) -> bool:
    """Исключает старую служебную таблицу из сравнения схемы."""
    if type_ == 'table' and name == 'schema_migrations':
        return False

    return True


def run_migrations_offline() -> None:
    """Генерирует SQL миграций без непосредственного подключения к базе."""
    context.configure(
        url=get_database_url().render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запускает миграции через подключение к PostgreSQL."""
    engine = create_engine(
        get_database_url(),
        poolclass=pool.NullPool,
    )

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_object=include_object,
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

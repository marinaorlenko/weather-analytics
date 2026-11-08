"""Фикстуры интеграционных тестов PostgreSQL.

Создаёт отдельную временную базу данных для тестирования ETL,
очищает таблицы между тестами и удаляет базу после завершения.
"""

from collections.abc import Iterator

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from weather_analytics.config import ConnectionParams, get_settings
from weather_analytics.db.models import Base
from weather_analytics.etl.loader import WeatherLoader

TEST_DATABASE = 'weather_analytics_test'


@pytest.fixture(scope='session')
def test_db_params() -> ConnectionParams:
    """Формирует безопасные параметры тестового подключения."""
    settings = get_settings()

    # Запрещаем совпадение рабочей и тестовой базы.
    if settings.db_name == TEST_DATABASE:
        pytest.fail(
            'Рабочая конфигурация указывает на тестовую базу. Проверь DB_NAME в .env.'
        )

    return {
        'host': settings.db_host,
        'port': settings.db_port,
        'user': settings.db_user,
        'password': settings.db_password,
        'dbname': TEST_DATABASE,
    }


@pytest.fixture(scope='session')
def test_database(
    test_db_params: ConnectionParams,
) -> Iterator[ConnectionParams]:
    """Создаёт временную PostgreSQL и удаляет её после тестов."""
    admin_params = {
        **test_db_params,
        'dbname': 'postgres',
    }

    database_created = False

    # CREATE DATABASE выполняется вне транзакции.
    with psycopg.connect(
        **admin_params,
        autocommit=True,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT 1 FROM pg_database WHERE datname = %s',
                (TEST_DATABASE,),
            )

            if cursor.fetchone() is not None:
                pytest.fail(
                    f'База {TEST_DATABASE} уже существует. '
                    'Автоматическое удаление запрещено.'
                )

            cursor.execute(
                sql.SQL('CREATE DATABASE {}').format(sql.Identifier(TEST_DATABASE))
            )
            database_created = True

    # Формируем URL для SQLAlchemy без ручной сборки строки.
    url = URL.create(
        drivername='postgresql+psycopg',
        username=test_db_params['user'],
        password=test_db_params['password'],
        host=test_db_params['host'],
        port=test_db_params['port'],
        database=test_db_params['dbname'],
    )

    engine = None

    try:
        engine = create_engine(url)

        # Создаём все таблицы по существующим SQLAlchemy-моделям.
        Base.metadata.create_all(engine)

        yield test_db_params

    finally:
        if engine is not None:
            engine.dispose()

        if database_created:
            # Закрываем оставшиеся соединения с временной базой.
            with psycopg.connect(
                **admin_params,
                autocommit=True,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = %s
                          AND pid <> pg_backend_pid()
                        """,
                        (TEST_DATABASE,),
                    )

                    cursor.execute(
                        sql.SQL('DROP DATABASE {}').format(
                            sql.Identifier(TEST_DATABASE)
                        )
                    )


@pytest.fixture(autouse=True)
def clean_database(
    request: pytest.FixtureRequest,
) -> Iterator[None]:
    """Очищает таблицы перед каждым интеграционным тестом."""
    if 'loader' not in request.fixturenames:
        yield
        return

    test_db_params = request.getfixturevalue('test_database')

    with psycopg.connect(**test_db_params) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE
                    historical_daily,
                    historical_hourly,
                    forecast_daily,
                    forecast_hourly,
                    forecast_ecmwf_hourly,
                    etl_state,
                    etl_runs,
                    cities
                RESTART IDENTITY CASCADE
                """
            )

    yield


@pytest.fixture
def loader(
    test_database: ConnectionParams,
) -> WeatherLoader:
    """Создаёт загрузчик с подключением только к тестовой базе."""
    weather_loader = WeatherLoader()

    # Явно заменяем подключения загрузчика и обоих репозиториев.
    weather_loader.connection_params = test_database
    weather_loader._weather.connection_params = test_database
    weather_loader._runs.connection_params = test_database

    return weather_loader


@pytest.fixture
def db_connection(
    test_database: ConnectionParams,
) -> Iterator[psycopg.Connection]:
    """Предоставляет подключение для проверки записанных данных."""
    with psycopg.connect(
        **test_database,
        autocommit=True,
    ) as connection:
        yield connection

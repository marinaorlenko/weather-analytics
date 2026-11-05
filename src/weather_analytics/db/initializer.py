"""Создание PostgreSQL и управление схемой через SQL и Alembic."""

import logging
from pathlib import Path
from typing import TypedDict

import psycopg
from alembic.config import Config
from psycopg import sql

from alembic import command
from weather_analytics.config import get_settings

logger = logging.getLogger(__name__)

BASELINE_REVISION = 'c9af41acf081'


class ConnectionParams(TypedDict):
    """Параметры подключения к PostgreSQL."""

    host: str
    port: int
    user: str
    password: str


class DatabaseInitializer:
    """Создаёт базу, начальную схему и применяет миграции Alembic."""

    def __init__(self) -> None:
        """Получает настройки PostgreSQL и пути к файлам схемы."""
        settings = get_settings()

        self.db_name = settings.db_name
        self.connection_params: ConnectionParams = {
            'host': settings.db_host,
            'port': settings.db_port,
            'user': settings.db_user,
            'password': settings.db_password,
        }

        # Все пути определяются относительно корня проекта.
        self.project_dir = Path(__file__).resolve().parents[3]
        self.initial_schema = (
            self.project_dir / 'sql' / 'migrations' / '001_initial_schema.sql'
        )
        self.alembic_ini = self.project_dir / 'alembic.ini'

    def create_database(self) -> None:
        """Создаёт базу PostgreSQL, если она ещё не существует."""
        with psycopg.connect(
            **self.connection_params,
            dbname='postgres',
            autocommit=True,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT 1 FROM pg_database WHERE datname = %s',
                    (self.db_name,),
                )

                if cursor.fetchone():
                    logger.info('База %s уже существует', self.db_name)
                    return

                cursor.execute(
                    sql.SQL('CREATE DATABASE {}').format(
                        sql.Identifier(self.db_name),
                    )
                )
                logger.info('Создана база %s', self.db_name)

    def _get_alembic_config(self) -> Config:
        """Возвращает конфигурацию Alembic с абсолютными путями."""
        if not self.alembic_ini.is_file():
            raise FileNotFoundError(
                f'Не найдена конфигурация Alembic: {self.alembic_ini}'
            )

        config = Config(str(self.alembic_ini))
        config.set_main_option(
            'script_location',
            str(self.project_dir / 'alembic'),
        )
        return config

    def _get_schema_state(self) -> str:
        """Определяет состояние таблиц в существующей базе."""
        with psycopg.connect(
            **self.connection_params,
            dbname=self.db_name,
        ) as connection:
            tables = connection.execute(
                '''
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                '''
            ).fetchall()

        table_names = {row[0] for row in tables}

        if 'alembic_version' in table_names:
            return 'versioned'

        if not table_names:
            return 'empty'

        return 'unversioned'

    def _create_initial_schema(self) -> None:
        """Создаёт таблицы из SQL-файла в пустой базе."""
        if not self.initial_schema.is_file():
            raise FileNotFoundError(
                f'Не найден SQL-файл: {self.initial_schema}'
            )

        schema_sql = self.initial_schema.read_text(encoding='utf-8')

        # Выполняем всю начальную схему в одной транзакции.
        with psycopg.connect(
            **self.connection_params,
            dbname=self.db_name,
        ) as connection:
            connection.execute(schema_sql)

        logger.info('Начальная схема PostgreSQL создана из SQL')

    def apply_migrations(self) -> None:
        """Создаёт начальную схему при необходимости и запускает Alembic."""
        config = self._get_alembic_config()
        schema_state = self._get_schema_state()

        if schema_state == 'empty':
            # Новая база: создаём исходные таблицы и фиксируем baseline.
            self._create_initial_schema()
            command.stamp(config, BASELINE_REVISION)
            logger.info('Зарегистрирована начальная ревизия Alembic')

        elif schema_state == 'unversioned':
            # Не регистрируем произвольную существующую схему автоматически.
            raise RuntimeError(
                'В PostgreSQL обнаружены таблицы без истории Alembic. '
                'Требуется проверить схему перед регистрацией baseline.'
            )

        # Применяем только миграции, отсутствующие в текущей базе.
        command.upgrade(config, 'head')
        logger.info('Миграции Alembic применены')

    def initialize(self) -> None:
        """Создаёт базу при необходимости и обновляет её схему."""
        self.create_database()
        self.apply_migrations()
        logger.info('Инициализация PostgreSQL завершена')

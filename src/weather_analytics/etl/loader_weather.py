"""Сохранение городов и погодных данных в PostgreSQL.

Модуль предоставляет операции записи и подсчёта погодных записей.
Каждая самостоятельная операция сохранения выполняется в транзакции.

Составные транзакции исторического ETL и прогнозных снимков
остаются в основном WeatherLoader.
"""

import logging
from typing import Any

import psycopg
from psycopg import sql

from weather_analytics.config import ConnectionParams
from weather_analytics.etl.loader_columns import (
    ECMWF_HOURLY_COLUMNS,
    FORECAST_DAILY_COLUMNS,
    FORECAST_HOURLY_COLUMNS,
    HISTORICAL_DAILY_COLUMNS,
    HISTORICAL_HOURLY_COLUMNS,
)
from weather_analytics.etl.loader_queries import (
    execute_batch,
    prepare_records,
)
from weather_analytics.models.weather import Location

logger = logging.getLogger(__name__)


class WeatherRepository:
    """Сохраняет города и погодные показатели в PostgreSQL."""

    def __init__(self, connection_params: ConnectionParams) -> None:
        """Принимает параметры подключения к базе данных.

        Args:
            connection_params: Параметры подключения для psycopg.
        """
        self.connection_params = connection_params

    def save_city(self, location: Location) -> int:
        """Создаёт или обновляет город и возвращает его идентификатор.

        Args:
            location: Географическая локация.

        Returns:
            Идентификатор города в PostgreSQL.

        Raises:
            RuntimeError: Если PostgreSQL не вернул идентификатор города.
        """
        query = """
            INSERT INTO cities (
                name,
                country,
                latitude,
                longitude,
                timezone
            )
            VALUES (
                %(name)s,
                %(country)s,
                %(latitude)s,
                %(longitude)s,
                %(timezone)s
            )
            ON CONFLICT (name, country)
            DO UPDATE SET
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                timezone = EXCLUDED.timezone
            RETURNING city_id;
        """

        params = {
            'name': location.name,
            'country': location.country,
            'latitude': location.latitude,
            'longitude': location.longitude,
            'timezone': location.timezone,
        }

        # Создаём или обновляем город в отдельной транзакции.
        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()

                if result is None:
                    raise RuntimeError(
                        f'Не удалось получить идентификатор города: {location.name}'
                    )

                city_id = result[0]

        logger.info(
            'Город сохранён: %s, %s (city_id=%s)',
            location.name,
            location.country,
            city_id,
        )

        return city_id

    def _save_records(
        self,
        city_id: int,
        records: list[dict[str, Any]],
        table: str,
        columns: tuple[str, ...],
        conflict_columns: tuple[str, ...],
        forecast_run_id: int | None = None,
    ) -> int:
        """Сохраняет пакет погодных записей в указанную таблицу.

        Args:
            city_id: Идентификатор города.
            records: Подготовленные погодные записи.
            table: Название таблицы PostgreSQL.
            columns: Столбцы погодных показателей.
            conflict_columns: Столбцы уникального ограничения.
            forecast_run_id: Идентификатор прогнозного ETL-запуска.

        Returns:
            Количество переданных на сохранение записей.
        """
        if not records:
            return 0

        # Прогнозные записи содержат идентификатор ETL-запуска.
        forecast = forecast_run_id is not None

        params = prepare_records(
            city_id=city_id,
            records=records,
            columns=columns,
            forecast_run_id=forecast_run_id,
        )

        # Один пакет сохраняется в одной транзакции.
        # Ошибка executemany приводит к откату всего пакета.
        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                execute_batch(
                    cursor=cursor,
                    table=table,
                    columns=columns,
                    conflict_columns=conflict_columns,
                    params=params,
                    forecast=forecast,
                )

        logger.info(
            'Погодные данные сохранены: таблица=%s, city_id=%s, записей=%s',
            table,
            city_id,
            len(records),
        )

        return len(records)

    def save_historical_daily(
        self,
        city_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет суточные исторические показатели."""
        return self._save_records(
            city_id=city_id,
            records=records,
            table='historical_daily',
            columns=HISTORICAL_DAILY_COLUMNS,
            conflict_columns=('city_id', 'weather_date'),
        )

    def save_historical_hourly(
        self,
        city_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет почасовые исторические показатели."""
        return self._save_records(
            city_id=city_id,
            records=records,
            table='historical_hourly',
            columns=HISTORICAL_HOURLY_COLUMNS,
            conflict_columns=('city_id', 'weather_time'),
        )

    def save_forecast_daily(
        self,
        city_id: int,
        forecast_run_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет суточный прогноз с идентификатором запуска."""
        return self._save_records(
            city_id=city_id,
            records=records,
            table='forecast_daily',
            columns=FORECAST_DAILY_COLUMNS,
            conflict_columns=(
                'city_id',
                'forecast_date',
                'fetched_at',
            ),
            forecast_run_id=forecast_run_id,
        )

    def save_forecast_hourly(
        self,
        city_id: int,
        forecast_run_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет почасовой прогноз с идентификатором запуска."""
        return self._save_records(
            city_id=city_id,
            records=records,
            table='forecast_hourly',
            columns=FORECAST_HOURLY_COLUMNS,
            conflict_columns=(
                'city_id',
                'forecast_time',
                'fetched_at',
            ),
            forecast_run_id=forecast_run_id,
        )

    def save_ecmwf_hourly(
        self,
        city_id: int,
        forecast_run_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет специализированные почасовые показатели ECMWF."""
        return self._save_records(
            city_id=city_id,
            records=records,
            table='forecast_ecmwf_hourly',
            columns=ECMWF_HOURLY_COLUMNS,
            conflict_columns=(
                'city_id',
                'forecast_time',
                'fetched_at',
            ),
            forecast_run_id=forecast_run_id,
        )

    def _count_records(self, table: str, city_id: int) -> int:
        """Возвращает количество записей города в указанной таблице.

        Args:
            table: Название таблицы PostgreSQL.
            city_id: Идентификатор города.

        Returns:
            Количество записей.

        Raises:
            RuntimeError: Если PostgreSQL не вернул результат подсчёта.
        """
        # Название таблицы передаётся через безопасный SQL Identifier.
        # Значение city_id остаётся параметром запроса.

        query = sql.SQL('SELECT COUNT(*) FROM {} WHERE city_id = %s').format(
            sql.Identifier(table)
        )

        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (city_id,))
                result = cursor.fetchone()

                if result is None:
                    raise RuntimeError(
                        f'Не удалось получить количество записей из {table}'
                    )

                count = result[0]

        return count

    def count_historical_daily(self, city_id: int) -> int:
        """Возвращает число суточных исторических записей."""
        return self._count_records('historical_daily', city_id)

    def count_historical_hourly(self, city_id: int) -> int:
        """Возвращает число почасовых исторических записей."""
        return self._count_records('historical_hourly', city_id)

    def count_forecast_records(self, city_id: int) -> tuple[int, int]:
        """Возвращает число суточных и почасовых прогнозных записей.

        Args:
            city_id: Идентификатор города.

        Returns:
            Кортеж из количества суточных и почасовых прогнозов.

        Raises:
            RuntimeError: Если PostgreSQL не вернул результаты подсчёта.
        """
        # Оба показателя получаем одним запросом,
        # чтобы не создавать два отдельных подключения.
        query = """
            SELECT
                (SELECT COUNT(*)
                 FROM forecast_daily
                 WHERE city_id = %(city_id)s),
                (SELECT COUNT(*)
                 FROM forecast_hourly
                 WHERE city_id = %(city_id)s);
        """

        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, {'city_id': city_id})
                result = cursor.fetchone()

                if result is None:
                    raise RuntimeError(
                        'Не удалось получить количество прогнозных записей'
                    )

                daily_count, hourly_count = result

        return daily_count, hourly_count

    def count_ecmwf_hourly(self, city_id: int) -> int:
        """Возвращает число почасовых прогнозных записей ECMWF."""
        return self._count_records('forecast_ecmwf_hourly', city_id)

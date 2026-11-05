"""Единый загрузчик погодных данных в PostgreSQL.

WeatherLoader объединяет репозитории погодных данных и ETL-запусков,
а также управляет составными транзакциями исторической загрузки
и сохранения прогнозных снимков.
"""

import logging
from datetime import date
from typing import Any

import psycopg

from weather_analytics.config import ConnectionParams, get_settings
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
from weather_analytics.etl.loader_runs import ETLRunRepository
from weather_analytics.etl.loader_weather import WeatherRepository
from weather_analytics.models.weather import Location

logger = logging.getLogger(__name__)


class WeatherLoader:
    """Предоставляет единый интерфейс сохранения данных ETL."""

    def __init__(self) -> None:
        """Создаёт репозитории с общими параметрами подключения."""
        settings = get_settings()

        self.connection_params: ConnectionParams = {
            'host': settings.db_host,
            'port': settings.db_port,
            'user': settings.db_user,
            'password': settings.db_password,
            'dbname': settings.db_name,
        }

        # Оба репозитория используют одну конфигурацию PostgreSQL.
        # Соединения создаются непосредственно при выполнении операций.
        self._weather = WeatherRepository(self.connection_params)
        self._runs = ETLRunRepository(self.connection_params)

    # ========================================================
    # ГОРОДА И ПОГОДНЫЕ ДАННЫЕ
    # ========================================================

    def save_city(self, location: Location) -> int:
        """Создаёт или обновляет город и возвращает его идентификатор."""
        return self._weather.save_city(location)

    def save_historical_daily(
        self,
        city_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет суточные исторические записи."""
        return self._weather.save_historical_daily(city_id, records)

    def save_historical_hourly(
        self,
        city_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет почасовые исторические записи."""
        return self._weather.save_historical_hourly(city_id, records)

    def save_forecast_daily(
        self,
        city_id: int,
        forecast_run_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет суточные прогнозные записи."""
        return self._weather.save_forecast_daily(
            city_id,
            forecast_run_id,
            records,
        )

    def save_forecast_hourly(
        self,
        city_id: int,
        forecast_run_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет почасовые прогнозные записи."""
        return self._weather.save_forecast_hourly(
            city_id,
            forecast_run_id,
            records,
        )

    def save_ecmwf_hourly(
        self,
        city_id: int,
        forecast_run_id: int,
        records: list[dict[str, Any]],
    ) -> int:
        """Сохраняет специализированные показатели ECMWF."""
        return self._weather.save_ecmwf_hourly(
            city_id,
            forecast_run_id,
            records,
        )

    def count_historical_daily(self, city_id: int) -> int:
        """Возвращает число суточных исторических записей."""
        return self._weather.count_historical_daily(city_id)

    def count_historical_hourly(self, city_id: int) -> int:
        """Возвращает число почасовых исторических записей."""
        return self._weather.count_historical_hourly(city_id)

    def count_forecast_records(self, city_id: int) -> tuple[int, int]:
        """Возвращает число суточных и почасовых прогнозных записей."""
        return self._weather.count_forecast_records(city_id)

    def count_ecmwf_hourly(self, city_id: int) -> int:
        """Возвращает число почасовых записей ECMWF."""
        return self._weather.count_ecmwf_hourly(city_id)

    # ========================================================
    # ЖУРНАЛ ETL И СОСТОЯНИЕ ЗАГРУЗКИ
    # ========================================================

    def start_run(self, pipeline: str) -> int:
        """Регистрирует ETL-запуск и возвращает его идентификатор."""
        return self._runs.start_run(pipeline)

    def finish_run(self, run_id: int, rows_loaded: int) -> None:
        """Отмечает успешное завершение ETL-запуска."""
        self._runs.finish_run(run_id, rows_loaded)

    def fail_run(self, run_id: int, error: Exception) -> None:
        """Регистрирует неудачное завершение ETL-запуска."""
        self._runs.fail_run(run_id, error)

    def get_last_loaded_date(self, city_id: int) -> date | None:
        """Возвращает последнюю успешно загруженную историческую дату."""
        return self._runs.get_last_loaded_date(city_id)

    def update_last_loaded_date(
        self,
        city_id: int,
        loaded_date: date,
    ) -> None:
        """Обновляет дату последней успешной исторической загрузки."""
        self._runs.update_last_loaded_date(city_id, loaded_date)

    # ========================================================
    # АТОМАРНОЕ СОХРАНЕНИЕ ПРОГНОЗА
    # ========================================================

    def save_forecast_snapshot(
        self,
        city_id: int,
        run_id: int,
        daily_records: list[dict[str, Any]],
        hourly_records: list[dict[str, Any]],
        ecmwf_records: list[dict[str, Any]],
    ) -> int:
        """Атомарно сохраняет три прогноза и завершает ETL-запуск.

        Args:
            city_id: Идентификатор города.
            run_id: Идентификатор прогнозного ETL-запуска.
            daily_records: Суточные прогнозные записи.
            hourly_records: Почасовые прогнозные записи.
            ecmwf_records: Специализированные показатели ECMWF.

        Returns:
            Общее количество переданных на сохранение записей.

        Raises:
            ValueError: Если активный прогнозный запуск не найден.
            psycopg.Error: Если произошла ошибка PostgreSQL.
        """
        run_query = '''
            UPDATE etl_runs
            SET
                finished_at = CURRENT_TIMESTAMP,
                status = 'success',
                rows_loaded = %(rows_loaded)s,
                error_message = NULL
            WHERE run_id = %(run_id)s
              AND pipeline = 'forecast'
              AND status = 'running'
            RETURNING run_id;
        '''

        # Подготавливаем три независимых набора параметров.
        # Идентификатор запуска включается в каждую запись.
        daily_params = prepare_records(
            city_id,
            daily_records,
            FORECAST_DAILY_COLUMNS,
            run_id,
        )

        hourly_params = prepare_records(
            city_id,
            hourly_records,
            FORECAST_HOURLY_COLUMNS,
            run_id,
        )

        ecmwf_params = prepare_records(
            city_id,
            ecmwf_records,
            ECMWF_HOURLY_COLUMNS,
            run_id,
        )

        rows_loaded = (
            len(daily_records)
            + len(hourly_records)
            + len(ecmwf_records)
        )

        # Все три таблицы и статус запуска обновляются
        # в рамках одного соединения и одной транзакции.
        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                execute_batch(
                    cursor,
                    'forecast_daily',
                    FORECAST_DAILY_COLUMNS,
                    ('city_id', 'forecast_date', 'fetched_at'),
                    daily_params,
                    forecast=True,
                )

                execute_batch(
                    cursor,
                    'forecast_hourly',
                    FORECAST_HOURLY_COLUMNS,
                    ('city_id', 'forecast_time', 'fetched_at'),
                    hourly_params,
                    forecast=True,
                )

                execute_batch(
                    cursor,
                    'forecast_ecmwf_hourly',
                    ECMWF_HOURLY_COLUMNS,
                    ('city_id', 'forecast_time', 'fetched_at'),
                    ecmwf_params,
                    forecast=True,
                )

                # Статус обновляем внутри той же транзакции.
                # Если запуск неактивен, исключение откатит
                # все вставленные прогнозные записи.
                cursor.execute(
                    run_query,
                    {
                        'run_id': run_id,
                        'rows_loaded': rows_loaded,
                    },
                )

                if cursor.fetchone() is None:
                    raise ValueError(
                        'Активный прогнозный ETL-запуск '
                        f'с run_id={run_id} не найден'
                    )

        logger.info(
            'Прогнозный снимок сохранён одной транзакцией: '
            'city_id=%s, run_id=%s, ежедневно=%s, '
            'почасово=%s, ECMWF=%s, всего=%s',
            city_id,
            run_id,
            len(daily_records),
            len(hourly_records),
            len(ecmwf_records),
            rows_loaded,
        )

        return rows_loaded

    # ========================================================
    # АТОМАРНОЕ СОХРАНЕНИЕ ИСТОРИИ
    # ========================================================

    def save_historical_period(
        self,
        city_id: int,
        run_id: int,
        daily_records: list[dict[str, Any]],
        hourly_records: list[dict[str, Any]],
        loaded_date: date,
    ) -> int:
        """Атомарно сохраняет историю, прогресс и результат ETL-запуска.

        Args:
            city_id: Идентификатор города.
            run_id: Идентификатор исторического ETL-запуска.
            daily_records: Суточные исторические записи.
            hourly_records: Почасовые исторические записи.
            loaded_date: Последняя дата успешно загружаемого периода.

        Returns:
            Общее количество переданных на сохранение записей.

        Raises:
            ValueError: Если активный исторический запуск не найден.
            psycopg.Error: Если произошла ошибка PostgreSQL.
        """
        state_query = '''
            INSERT INTO etl_state (
                pipeline,
                city_id,
                last_loaded_date,
                last_loaded_at
            )
            VALUES ('historical', %s, %s, NOW())
            ON CONFLICT (pipeline, city_id)
            DO UPDATE SET
                last_loaded_date = GREATEST(
                    etl_state.last_loaded_date,
                    EXCLUDED.last_loaded_date
                ),
                last_loaded_at = NOW(),
                updated_at = NOW();
        '''

        run_query = '''
            UPDATE etl_runs
            SET
                finished_at = CURRENT_TIMESTAMP,
                status = 'success',
                rows_loaded = %s,
                error_message = NULL
            WHERE run_id = %s
              AND pipeline = 'historical'
              AND status = 'running'
            RETURNING run_id;
        '''

        # Подготавливаем суточные и почасовые записи
        # с единым идентификатором города.
        daily_params = prepare_records(
            city_id,
            daily_records,
            HISTORICAL_DAILY_COLUMNS,
        )

        hourly_params = prepare_records(
            city_id,
            hourly_records,
            HISTORICAL_HOURLY_COLUMNS,
        )

        rows_loaded = len(daily_records) + len(hourly_records)

        # Исторические записи, состояние загрузки и статус
        # ETL-запуска должны сохраниться либо все вместе,
        # либо не сохраниться вовсе.
        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                execute_batch(
                    cursor,
                    'historical_daily',
                    HISTORICAL_DAILY_COLUMNS,
                    ('city_id', 'weather_date'),
                    daily_params,
                )

                execute_batch(
                    cursor,
                    'historical_hourly',
                    HISTORICAL_HOURLY_COLUMNS,
                    ('city_id', 'weather_time'),
                    hourly_params,
                )

                # Обновляем прогресс внутри той же транзакции.
                cursor.execute(
                    state_query,
                    (city_id, loaded_date),
                )

                # Успешное завершение запуска фиксируем
                # только после всех операций сохранения.
                cursor.execute(
                    run_query,
                    (rows_loaded, run_id),
                )

                if cursor.fetchone() is None:
                    raise ValueError(
                        'Активный исторический ETL-запуск '
                        f'с run_id={run_id} не найден'
                    )

        logger.info(
            'Исторический период сохранён одной транзакцией: '
            'city_id=%s, run_id=%s, дата=%s, записей=%s',
            city_id,
            run_id,
            loaded_date,
            rows_loaded,
        )

        return rows_loaded

"""Интеграционные тесты загрузчика погодных данных PostgreSQL."""

from datetime import UTC, date, datetime

import psycopg
import pytest

from weather_analytics.etl.loader import WeatherLoader
from weather_analytics.models.weather import Location


@pytest.fixture
def city_id(loader: WeatherLoader) -> int:
    """Создаёт тестовый город и возвращает его идентификатор."""
    return loader.save_city(
        Location(
            name='Dubai',
            country='United Arab Emirates',
            latitude=25.07725,
            longitude=55.30927,
            timezone='Asia/Dubai',
        )
    )


def test_save_city_upsert(
    loader: WeatherLoader,
    db_connection: psycopg.Connection,
) -> None:
    """Проверяет создание и обновление города без дублирования."""
    location = Location(
        name='Dubai',
        country='United Arab Emirates',
        latitude=25.07725,
        longitude=55.30927,
        timezone='Asia/Dubai',
    )

    first_id = loader.save_city(location)

    location.latitude = 25.2
    second_id = loader.save_city(location)

    with db_connection.cursor() as cursor:
        cursor.execute(
            'SELECT latitude FROM cities WHERE city_id = %s',
            (first_id,),
        )
        latitude = cursor.fetchone()[0]

    assert first_id == second_id
    assert latitude == 25.2


@pytest.mark.parametrize(
    ('method_name', 'table', 'time_column', 'time_value'),
    [
        (
            'save_historical_daily',
            'historical_daily',
            'weather_date',
            date(2026, 10, 1),
        ),
        (
            'save_historical_hourly',
            'historical_hourly',
            'weather_time',
            datetime(2026, 10, 1, tzinfo=UTC),
        ),
    ],
)
def test_save_historical_upsert(
    loader: WeatherLoader,
    db_connection: psycopg.Connection,
    city_id: int,
    method_name: str,
    table: str,
    time_column: str,
    time_value: date | datetime,
) -> None:
    """Проверяет повторную загрузку истории без дублирования."""
    method = getattr(loader, method_name)

    record = {
        time_column: time_value,
        'temperature_min' if table == 'historical_daily' else 'temperature': 25.0,
    }

    assert method(city_id, [record]) == 1

    # Повторная загрузка должна обновить показатель.
    metric = 'temperature_min' if table == 'historical_daily' else 'temperature'
    record[metric] = 30.0

    assert method(city_id, [record]) == 1

    # Названия таблицы и столбца берутся только из фиксированных тестовых данных.
    with db_connection.cursor() as cursor:
        from psycopg import sql

        query = sql.SQL(
            'SELECT COUNT(*), MAX({metric}) FROM {table} WHERE city_id = %s'
        ).format(
            metric=sql.Identifier(metric),
            table=sql.Identifier(table),
        )
        cursor.execute(query, (city_id,))
        count, value = cursor.fetchone()

    assert count == 1
    assert value == 30.0


def test_save_forecast_snapshot(
    loader: WeatherLoader,
    db_connection: psycopg.Connection,
    city_id: int,
) -> None:
    """Проверяет атомарное сохранение трёх прогнозных таблиц."""
    run_id = loader.start_run('forecast')
    fetched_at = datetime(2026, 10, 29, 6, tzinfo=UTC)
    forecast_time = datetime(2026, 10, 30, 10, tzinfo=UTC)

    rows_loaded = loader.save_forecast_snapshot(
        city_id=city_id,
        run_id=run_id,
        daily_records=[{
            'forecast_date': date(2026, 10, 30),
            'fetched_at': fetched_at,
            'temperature_min': 24.0,
        }],
        hourly_records=[{
            'forecast_time': forecast_time,
            'fetched_at': fetched_at,
            'temperature': 30.5,
        }],
        ecmwf_records=[{
            'forecast_time': forecast_time,
            'fetched_at': fetched_at,
            'cape': 150.0,
        }],
    )

    with db_connection.cursor() as cursor:
        cursor.execute(
            'SELECT status, rows_loaded FROM etl_runs WHERE run_id = %s',
            (run_id,),
        )
        status, saved_count = cursor.fetchone()

    assert rows_loaded == 3
    assert loader.count_forecast_records(city_id) == (1, 1)
    assert loader.count_ecmwf_hourly(city_id) == 1
    assert (status, saved_count) == ('success', 3)


def test_forecast_snapshot_rollback(
    loader: WeatherLoader,
    db_connection: psycopg.Connection,
    city_id: int,
) -> None:
    """Проверяет откат прогнозных записей при ошибке ECMWF."""
    run_id = loader.start_run('forecast')
    fetched_at = datetime(2026, 10, 29, 6, tzinfo=UTC)
    forecast_time = datetime(2026, 10, 30, 10, tzinfo=UTC)

    # Недопустимый тип значения вызывает ошибку PostgreSQL.
    with pytest.raises(psycopg.Error):
        loader.save_forecast_snapshot(
            city_id=city_id,
            run_id=run_id,
            daily_records=[{
                'forecast_date': date(2026, 10, 30),
                'fetched_at': fetched_at,
                'temperature_min': 24.0,
            }],
            hourly_records=[{
                'forecast_time': forecast_time,
                'fetched_at': fetched_at,
                'temperature': 30.5,
            }],
            ecmwf_records=[{
                'forecast_time': forecast_time,
                'fetched_at': fetched_at,
                'cape': 'invalid',
            }],
        )

    assert loader.count_forecast_records(city_id) == (0, 0)
    assert loader.count_ecmwf_hourly(city_id) == 0

    with db_connection.cursor() as cursor:
        cursor.execute(
            'SELECT status FROM etl_runs WHERE run_id = %s',
            (run_id,),
        )
        status = cursor.fetchone()[0]

    assert status == 'running'


def test_historical_period_and_progress(
    loader: WeatherLoader,
    city_id: int,
) -> None:
    """Проверяет сохранение истории и защиту прогресса от отката."""
    run_id = loader.start_run('historical')

    rows_loaded = loader.save_historical_period(
        city_id=city_id,
        run_id=run_id,
        daily_records=[{
            'weather_date': date(2026, 10, 1),
            'temperature_min': 25.0,
        }],
        hourly_records=[{
            'weather_time': datetime(
                2026, 10, 1, tzinfo=UTC,
            ),
            'temperature': 28.5,
        }],
        loaded_date=date(2026, 10, 1),
    )

    assert rows_loaded == 2
    assert loader.count_historical_daily(city_id) == 1
    assert loader.count_historical_hourly(city_id) == 1
    assert loader.get_last_loaded_date(city_id) == date(2026, 10, 1)

    # Более ранняя дата не должна уменьшать прогресс.
    loader.update_last_loaded_date(city_id, date(2026, 9, 1))

    assert loader.get_last_loaded_date(city_id) == date(2026, 10, 1)


def test_historical_period_rollback(
    loader: WeatherLoader,
    city_id: int,
) -> None:
    """Проверяет откат истории и прогресса при неактивном запуске."""
    run_id = loader.start_run('historical')
    loader.finish_run(run_id, 0)

    with pytest.raises(ValueError, match='не найден'):
        loader.save_historical_period(
            city_id=city_id,
            run_id=run_id,
            daily_records=[{
                'weather_date': date(2026, 10, 1),
                'temperature_min': 25.0,
            }],
            hourly_records=[],
            loaded_date=date(2026, 10, 1),
        )

    assert loader.count_historical_daily(city_id) == 0
    assert loader.get_last_loaded_date(city_id) is None


def test_etl_run_statuses(
    loader: WeatherLoader,
    db_connection: psycopg.Connection,
) -> None:
    """Проверяет успешное и неудачное завершение ETL-запусков."""
    success_id = loader.start_run('historical')
    failed_id = loader.start_run('forecast')

    loader.finish_run(success_id, 25)
    loader.fail_run(failed_id, RuntimeError('Ошибка API'))

    with db_connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT run_id, status, rows_loaded, error_message
            FROM etl_runs
            WHERE run_id IN (%s, %s)
            ''',
            (success_id, failed_id),
        )
        results = {row[0]: row[1:] for row in cursor.fetchall()}

    assert results[success_id] == ('success', 25, None)
    assert results[failed_id] == ('failed', 0, 'Ошибка API')

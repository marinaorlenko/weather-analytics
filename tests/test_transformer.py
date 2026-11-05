"""Тесты преобразования погодных данных для PostgreSQL."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from weather_analytics.etl.field_mappings import (
    ECMWF_HOURLY_FIELDS,
    FORECAST_DAILY_FIELDS,
    FORECAST_HOURLY_FIELDS,
    HISTORICAL_DAILY_FIELDS,
    HISTORICAL_HOURLY_FIELDS,
)
from weather_analytics.etl.loader_columns import (
    ECMWF_HOURLY_COLUMNS,
    FORECAST_DAILY_COLUMNS,
    FORECAST_HOURLY_COLUMNS,
    HISTORICAL_DAILY_COLUMNS,
    HISTORICAL_HOURLY_COLUMNS,
)
from weather_analytics.etl.transformer import WeatherTransformer
from weather_analytics.models.weather import Location


@pytest.fixture
def location() -> Location:
    """Создаёт тестовую локацию с часовым поясом Дубая."""
    return Location(
        name='Dubai',
        country='United Arab Emirates',
        latitude=25.07725,
        longitude=55.30927,
        timezone='Asia/Dubai',
    )


def test_transform_historical_daily(location: Location) -> None:
    """Проверяет преобразование ежедневных исторических данных."""
    data = {
        'daily': {
            'time': ['2026-10-01', '2026-10-02'],
            'temperature_2m_min': [25.0, 24.5],
            'temperature_2m_max': [35.0, 34.0],
            'precipitation_sum': [0.0, None],
            'wind_speed_10m_max': [15.2, 12.8],
        }
    }

    result = WeatherTransformer.transform_historical_daily(location, data)

    # Проверяем преобразование дат и основных погодных показателей.
    assert len(result) == 2
    assert result[0]['weather_date'] == date(2026, 10, 1)
    assert result[1]['weather_date'] == date(2026, 10, 2)
    assert result[0]['temperature_min'] == 25.0
    assert result[0]['temperature_max'] == 35.0
    assert result[0]['precipitation'] == 0.0
    assert result[0]['wind_speed_max'] == 15.2

    # Отсутствующее значение показателя сохраняется как None.
    assert result[1]['precipitation'] is None


def test_transform_historical_hourly(location: Location) -> None:
    """Проверяет преобразование почасовых данных и Unix timestamps."""
    data = {
        'hourly': {
            'time': [1790812800, 1790816400],
            'temperature_2m': [28.5, 28.1],
            'relative_humidity_2m': [65, None],
            'precipitation': [0.0, 0.0],
            'wind_speed_10m': [12.4, 11.8],
        }
    }

    result = WeatherTransformer.transform_historical_hourly(location, data)

    # Проверяем преобразование показателей и сохранение None.
    assert len(result) == 2
    assert result[0]['temperature'] == 28.5
    assert result[0]['humidity'] == 65
    assert result[1]['humidity'] is None
    assert result[1]['wind_speed'] == 11.8

    # Абсолютное время должно сохраняться в UTC.
    expected_time = datetime.fromtimestamp(
        1790812800,
        tz=UTC,
    )

    assert result[0]['weather_time'] == expected_time
    assert result[0]['weather_time'].utcoffset() == timedelta(0)


def test_transform_historical_hourly_dst() -> None:
    """Проверяет сохранение двух разных часов при переходе на зимнее время."""
    location = Location(
        name='Paris',
        country='France',
        latitude=48.8566,
        longitude=2.3522,
        timezone='Europe/Paris',
    )

    # В Париже 25 октября 2026 года час 02:00 повторяется дважды.
    # Первый соответствует 00:00 UTC, второй — 01:00 UTC.
    timestamps = [
        int(datetime(2026, 10, 25, 0, tzinfo=UTC).timestamp()),
        int(datetime(2026, 10, 25, 1, tzinfo=UTC).timestamp()),
    ]

    data = {
        'hourly': {
            'time': timestamps,
            'temperature_2m': [12.0, 11.5],
            'relative_humidity_2m': [80, 82],
            'precipitation': [0.0, 0.0],
            'wind_speed_10m': [8.0, 7.5],
        }
    }

    result = WeatherTransformer.transform_historical_hourly(location, data)

    # Оба наблюдения должны сохраниться как разные моменты UTC.
    assert len(result) == 2
    assert result[0]['weather_time'] != result[1]['weather_time']

    # При переводе в парижское время оба наблюдения относятся к 02:00.
    paris_timezone = ZoneInfo('Europe/Paris')

    first_local = result[0]['weather_time'].astimezone(paris_timezone)
    second_local = result[1]['weather_time'].astimezone(paris_timezone)

    assert first_local.hour == 2
    assert second_local.hour == 2

    # Различаются смещение UTC и признак повторного часа fold.
    assert first_local.utcoffset() == timedelta(hours=2)
    assert second_local.utcoffset() == timedelta(hours=1)
    assert first_local.fold == 0
    assert second_local.fold == 1


def test_transform_forecast_daily(location: Location) -> None:
    """Проверяет преобразование ежедневного прогноза погоды."""
    fetched_at = datetime(2026, 10, 29, 6, 0, tzinfo=UTC)

    data = {
        'daily': {
            'time': ['2026-10-30', '2026-10-31'],
            'temperature_2m_min': [24.0, 23.5],
            'temperature_2m_max': [33.0, 32.5],
            'precipitation_sum': [0.0, None],
            'wind_speed_10m_max': [14.0, 12.5],
        }
    }

    result = WeatherTransformer.transform_forecast_daily(
        location,
        data,
        fetched_at,
    )

    # Проверяем даты и основные погодные показатели.
    assert len(result) == 2
    assert result[0]['forecast_date'] == date(2026, 10, 30)
    assert result[1]['forecast_date'] == date(2026, 10, 31)
    assert result[0]['temperature_min'] == 24.0
    assert result[0]['temperature_max'] == 33.0
    assert result[0]['wind_speed_max'] == 14.0
    assert result[1]['precipitation'] is None

    # Все записи одного прогноза имеют одинаковое время получения.
    assert all(row['fetched_at'] == fetched_at for row in result)


def test_transform_forecast_hourly(location: Location) -> None:
    """Проверяет преобразование почасового прогноза в UTC."""
    fetched_at = datetime(2026, 10, 29, 6, 0, tzinfo=UTC)

    data = {
        'hourly': {
            'time': [1790812800, 1790816400],
            'temperature_2m': [28.5, 28.1],
            'relative_humidity_2m': [65, None],
            'precipitation': [0.0, 0.0],
            'wind_speed_10m': [12.4, 11.8],
        }
    }

    result = WeatherTransformer.transform_forecast_hourly(
        location,
        data,
        fetched_at,
    )

    # Проверяем преобразование показателей.
    assert len(result) == 2
    assert result[0]['temperature'] == 28.5
    assert result[0]['humidity'] == 65
    assert result[1]['humidity'] is None
    assert result[1]['wind_speed'] == 11.8

    # Проверяем временную метку прогноза.
    expected_time = datetime.fromtimestamp(
        1790812800,
        tz=UTC,
    )

    assert result[0]['forecast_time'] == expected_time
    assert result[0]['forecast_time'].utcoffset() == timedelta(0)

    # Время получения одинаково для всех почасовых записей.
    assert all(row['fetched_at'] == fetched_at for row in result)


def test_transform_forecast_invalid_fetched_at(location: Location) -> None:
    """Проверяет отказ от времени получения без часового пояса."""
    fetched_at = datetime(2026, 10, 29, 6, 0)

    daily_data = {'daily': {'time': []}}
    hourly_data = {'hourly': {'time': []}}

    # Наивный datetime недопустим для снимка прогноза.
    with pytest.raises(
        ValueError,
        match='Время получения прогноза должно содержать часовой пояс',
    ):
        WeatherTransformer.transform_forecast_daily(
            location,
            daily_data,
            fetched_at,
        )

    with pytest.raises(
        ValueError,
        match='Время получения прогноза должно содержать часовой пояс',
    ):
        WeatherTransformer.transform_forecast_hourly(
            location,
            hourly_data,
            fetched_at,
        )


@pytest.mark.parametrize(
    ('mapping', 'columns', 'special_columns'),
    [
        (
            HISTORICAL_DAILY_FIELDS,
            HISTORICAL_DAILY_COLUMNS,
            {'weather_date', 'sunrise', 'sunset'},
        ),
        (
            HISTORICAL_HOURLY_FIELDS,
            HISTORICAL_HOURLY_COLUMNS,
            {'weather_time', 'is_day'},
        ),
        (
            FORECAST_DAILY_FIELDS,
            FORECAST_DAILY_COLUMNS,
            {'forecast_date', 'fetched_at', 'sunrise', 'sunset'},
        ),
        (
            FORECAST_HOURLY_FIELDS,
            FORECAST_HOURLY_COLUMNS,
            {'forecast_time', 'fetched_at', 'is_day'},
        ),
        (
            ECMWF_HOURLY_FIELDS,
            ECMWF_HOURLY_COLUMNS,
            {'forecast_time', 'fetched_at'},
        ),
    ],
)
def test_mapping_matches_database_columns(
    mapping: dict[str, str],
    columns: tuple[str, ...],
    special_columns: set[str],
) -> None:
    """Проверяет согласованность полей API и столбцов PostgreSQL."""
    # Все поля трансформера должны существовать в целевой таблице.
    assert set(mapping.values()).issubset(set(columns))

    # Каждый столбец должен заполняться трансформером
    # либо относиться к специально обрабатываемым полям.
    assert set(columns) == set(mapping.values()) | special_columns


def test_transform_incomplete_field_array(location: Location) -> None:
    """Проверяет информативную ошибку для неполного массива."""
    data = {
        'daily': {
            'time': ['2026-10-01', '2026-10-02'],
            'temperature_2m_min': [25.0],
        },
    }

    # Массив температуры короче массива календарных дат.
    with pytest.raises(
        ValueError,
        match='temperature_2m_min',
    ):
        WeatherTransformer.transform_historical_daily(location, data)


def test_transform_missing_optional_field(location: Location) -> None:
    """Проверяет сохранение отсутствующего показателя как None."""
    data = {
        'daily': {
            'time': ['2026-10-01'],
        },
    }

    result = WeatherTransformer.transform_historical_daily(
        location,
        data,
    )

    # Отсутствующие необязательные поля не должны вызывать ошибку.
    assert result[0]['temperature_min'] is None
    assert result[0]['precipitation'] is None
    assert result[0]['sunrise'] is None


def test_transform_ecmwf_hourly(location: Location) -> None:
    """Проверяет преобразование специализированного прогноза ECMWF."""
    fetched_at = datetime(2026, 10, 29, 6, 0, tzinfo=UTC)
    timestamp = 1790812800

    data = {
        'hourly': {
            'time': [timestamp],
            'precipitation_type': [3],
            'cape': [150.0],
            'lightning_density': [None],
        },
    }

    result = WeatherTransformer.transform_ecmwf_hourly(
        location,
        data,
        fetched_at,
    )

    # Проверяем временную метку и время получения прогноза.
    assert len(result) == 1
    assert result[0]['forecast_time'] == datetime.fromtimestamp(
        timestamp,
        tz=UTC,
    )
    assert result[0]['fetched_at'] == fetched_at

    # Проверяем специализированные показатели ECMWF.
    assert result[0]['precipitation_type'] == 3
    assert result[0]['cape'] == 150.0
    assert result[0]['lightning_density'] is None
    assert result[0]['convective_inhibition'] is None

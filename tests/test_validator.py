"""Тесты проверки полноты исторических погодных данных."""

from datetime import UTC, date, datetime, timedelta

import pytest

from weather_analytics.etl.validator import validate_historical_records
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


@pytest.fixture
def historical_records() -> tuple[list[dict], list[dict]]:
    """Создаёт полный набор наблюдений за два дня."""
    start_date = date(2026, 10, 1)

    # Формируем две последовательные календарные даты.
    daily_records = [
        {'weather_date': start_date + timedelta(days=offset)}
        for offset in range(2)
    ]

    # Полночь 1 октября в Дубае соответствует 20:00 UTC 30 сентября.
    start_utc = datetime(2026, 9, 30, 20, tzinfo=UTC)

    hourly_records = [
        {'weather_time': start_utc + timedelta(hours=offset)}
        for offset in range(48)
    ]

    return daily_records, hourly_records


def test_validate_complete_historical_records(
    location: Location,
    historical_records: tuple[list[dict], list[dict]],
) -> None:
    """Проверяет успешную валидацию полного периода."""
    daily_records, hourly_records = historical_records

    validate_historical_records(
        location=location,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 2),
        daily_records=daily_records,
        hourly_records=hourly_records,
    )


@pytest.mark.parametrize(
    ('record_type', 'error_message'),
    [
        ('daily', 'Неполные или некорректные суточные данные'),
        ('hourly', 'Неполные или некорректные почасовые данные'),
    ],
)
def test_validate_incomplete_records(
    location: Location,
    historical_records: tuple[list[dict], list[dict]],
    record_type: str,
    error_message: str,
) -> None:
    """Проверяет обнаружение недостающих суточных и почасовых записей."""
    daily_records, hourly_records = historical_records

    # Удаляем последнюю запись только из проверяемого набора.
    if record_type == 'daily':
        daily_records = daily_records[:-1]
    else:
        hourly_records = hourly_records[:-1]

    with pytest.raises(ValueError, match=error_message):
        validate_historical_records(
            location=location,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            daily_records=daily_records,
            hourly_records=hourly_records,
        )


def test_validate_invalid_date_range(location: Location) -> None:
    """Проверяет обработку неправильного диапазона дат."""
    with pytest.raises(ValueError, match='Начальная дата'):
        validate_historical_records(
            location=location,
            start_date=date(2026, 10, 2),
            end_date=date(2026, 10, 1),
            daily_records=[],
            hourly_records=[],
        )

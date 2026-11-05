"""Проверка полноты исторических погодных данных."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from weather_analytics.models.weather import Location


def validate_historical_records(
    location: Location,
    start_date: date,
    end_date: date,
    daily_records: list[dict[str, Any]],
    hourly_records: list[dict[str, Any]],
) -> None:
    """Проверяет полноту и непрерывность исторических наблюдений.

    Args:
        location: Географическая локация с часовым поясом.
        start_date: Начальная дата исторического периода.
        end_date: Конечная дата исторического периода.
        daily_records: Преобразованные суточные записи.
        hourly_records: Преобразованные почасовые записи.

    Raises:
        ValueError: Если период некорректен, отсутствуют наблюдения,
            обнаружены дубликаты или неверные временные метки.
    """
    if start_date > end_date:
        raise ValueError('Начальная дата не может быть позже конечной')

    # Формируем ожидаемый набор календарных дат.
    expected_days = (end_date - start_date).days + 1
    expected_dates = {
        start_date + timedelta(days=offset)
        for offset in range(expected_days)
    }

    actual_dates = [record.get('weather_date') for record in daily_records]

    # Проверяем количество, уникальность и полноту суточных записей.
    if len(actual_dates) != expected_days or set(actual_dates) != expected_dates:
        raise ValueError(
            'Неполные или некорректные суточные данные: '
            f'ожидалось {expected_days} дат, '
            f'получено {len(actual_dates)} записей'
        )

    # Определяем границы локального периода и переводим их в UTC.
    # Это позволяет учитывать сутки продолжительностью 23 или 25 часов.
    city_timezone = ZoneInfo(location.timezone)

    start_utc = datetime.combine(
        start_date,
        time.min,
        tzinfo=city_timezone,
    ).astimezone(UTC)

    end_utc = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=city_timezone,
    ).astimezone(UTC)

    # Формируем ожидаемые почасовые метки в UTC.
    # В UTC переходов между летним и зимним временем нет.
    expected_hours = int(
        (end_utc - start_utc).total_seconds() // 3600
    )

    expected_timestamps = {
        start_utc + timedelta(hours=offset)
        for offset in range(expected_hours)
    }

    actual_timestamps = [
        record.get('weather_time')
        for record in hourly_records
    ]

    # Проверяем количество, уникальность и непрерывность часов.
    if (
        len(actual_timestamps) != expected_hours
        or set(actual_timestamps) != expected_timestamps
    ):
        raise ValueError(
            'Неполные или некорректные почасовые данные: '
            f'ожидалось {expected_hours} часов, '
            f'получено {len(actual_timestamps)} записей'
        )

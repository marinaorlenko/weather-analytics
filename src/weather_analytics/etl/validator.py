"""Проверка полноты исторических погодных данных."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

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
        start_date + timedelta(days=offset) for offset in range(expected_days)
    }

    actual_dates = [record.get('weather_date') for record in daily_records]

    # Проверяем количество, уникальность и полноту суточных записей.
    if len(actual_dates) != expected_days or set(actual_dates) != expected_dates:
        raise ValueError(
            'Неполные или некорректные суточные данные: '
            f'ожидалось {expected_days} дат, '
            f'получено {len(actual_dates)} записей'
        )

    # Историческая выгрузка Open-Meteo в текущей конфигурации
    # содержит 24 почасовые записи на каждый календарный день.
    # Не рассчитываем число часов через локальные границы месяца:
    # переходы на летнее время создают расхождение на один час.
    expected_hours = expected_days * 24

    actual_timestamps = [record.get('weather_time') for record in hourly_records]

    # Сначала проверяем количество записей.
    if len(actual_timestamps) != expected_hours:
        raise ValueError(
            'Неполные или некорректные почасовые данные: '
            f'ожидалось {expected_hours} часов, '
            f'получено {len(actual_timestamps)} записей'
        )

    # Временные метки должны быть datetime с часовым поясом.
    # Трансформер сохраняет исторические метки в UTC.
    if any(
        not isinstance(timestamp, datetime)
        or timestamp.tzinfo is None
        or timestamp.utcoffset() is None
        or timestamp.utcoffset() != timedelta(0)
        for timestamp in actual_timestamps
    ):
        raise ValueError(
            'Некорректные почасовые данные: '
            'временные метки должны содержать часовой пояс UTC'
        )

    # Проверяем отсутствие дубликатов и непрерывность ряда.
    # Сортировка позволяет не зависеть от порядка записей API.
    sorted_timestamps = sorted(
        timestamp.astimezone(UTC) for timestamp in actual_timestamps
    )

    if any(
        current - previous != timedelta(hours=1)
        for previous, current in zip(
            sorted_timestamps,
            sorted_timestamps[1:],
            strict=False,
        )
    ):
        raise ValueError(
            'Неполные или некорректные почасовые данные: '
            'обнаружены пропуски или дубликаты временных меток'
        )

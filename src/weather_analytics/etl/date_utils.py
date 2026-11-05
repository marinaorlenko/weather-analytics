"""Вспомогательные функции для обработки периодов загрузки."""

from calendar import monthrange
from datetime import date, timedelta


def split_date_range(
    start_date: date,
    end_date: date,
) -> list[tuple[date, date]]:
    """Разбивает диапазон дат на интервалы по календарным месяцам.

    Args:
        start_date: Начальная дата периода.
        end_date: Конечная дата периода.

    Returns:
        Список кортежей с начальной и конечной датами интервалов.

    Raises:
        ValueError: Если начальная дата позже конечной.
    """
    if start_date > end_date:
        raise ValueError('Начальная дата не может быть позже конечной')

    periods: list[tuple[date, date]] = []
    current_date = start_date

    # Последовательно формируем интервалы до конца заданного периода.
    while current_date <= end_date:
        # Определяем последний календарный день текущего месяца.
        last_day = monthrange(
            current_date.year,
            current_date.month,
        )[1]

        month_end = date(
            current_date.year,
            current_date.month,
            last_day,
        )

        # Последний интервал может закончиться раньше конца месяца.
        period_end = min(month_end, end_date)

        periods.append((current_date, period_end))

        # Следующий интервал начинается на следующий день.
        current_date = period_end + timedelta(days=1)

    return periods

"""Тесты разбиения исторических периодов на месяцы."""

from datetime import date

import pytest

from weather_analytics.etl.date_utils import split_date_range


@pytest.mark.parametrize(
    ('start_date', 'end_date', 'expected'),
    [
        (
            date(2026, 1, 15),
            date(2026, 4, 10),
            [
                (date(2026, 1, 15), date(2026, 1, 31)),
                (date(2026, 2, 1), date(2026, 2, 28)),
                (date(2026, 3, 1), date(2026, 3, 31)),
                (date(2026, 4, 1), date(2026, 4, 10)),
            ],
        ),
        (
            date(2026, 10, 1),
            date(2026, 10, 15),
            [
                (date(2026, 10, 1), date(2026, 10, 15)),
            ],
        ),
        (
            date(2024, 2, 27),
            date(2024, 3, 2),
            [
                (date(2024, 2, 27), date(2024, 2, 29)),
                (date(2024, 3, 1), date(2024, 3, 2)),
            ],
        ),
        (
            date(2026, 10, 1),
            date(2026, 10, 1),
            [
                (date(2026, 10, 1), date(2026, 10, 1)),
            ],
        ),
    ],
)
def test_split_date_range(start_date, end_date, expected):
    """Проверяет разбиение периодов с учётом границ месяцев."""
    result = split_date_range(start_date, end_date)

    assert result == expected


def test_split_date_range_invalid_period():
    """Проверяет ошибку при неправильном порядке дат."""
    with pytest.raises(ValueError, match='Начальная дата'):
        split_date_range(
            date(2026, 10, 10),
            date(2026, 10, 1),
        )

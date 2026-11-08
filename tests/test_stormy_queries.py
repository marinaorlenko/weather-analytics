"""Проверки русскоязычных запросов Stormy без обращения к API."""

import pytest

from weather_analytics.bot.parser import parse_query


@pytest.mark.parametrize(
    ('text', 'metric', 'period', 'city'),
    [
        ('Снег в Наро-Фоминске в ближайшую неделю', 'snow', 'week', 'Наро-Фоминске'),
        ('Дождь в Серпухове завтра', 'rain', 'day', 'Серпухове'),
        ('Гроза в Наро-Фоминске завтра', 'thunderstorm', 'day', 'Наро-Фоминске'),
        (
            'Температура в Великом Новгороде на выходных',
            'temperature',
            'weekend',
            'Великом Новгороде',
        ),
    ],
)
def test_weather_phenomena(
    text: str,
    metric: str,
    period: str,
    city: str,
) -> None:
    """Проверяет распознавание погодных явлений, периодов и городов."""
    query = parse_query(text)

    assert metric in query.metrics
    assert query.period == period
    assert query.city == city


def test_week_before_city() -> None:
    """Проверяет, что временная конструкция не принимается за название города."""
    query = parse_query('Снег в ближайшую неделю в Наро-Фоминске')

    assert query.city == 'Наро-Фоминске'

"""Тесты извлечения исторических и прогнозных погодных данных."""

from datetime import date
from unittest.mock import Mock

import pytest

from weather_analytics.etl.extractor import WeatherExtractor
from weather_analytics.models.weather import Location


@pytest.fixture
def location() -> Location:
    """Создаёт тестовую локацию."""
    return Location(
        name='Dubai',
        country='United Arab Emirates',
        latitude=25.07725,
        longitude=55.30927,
        timezone='Asia/Dubai',
    )


def test_extract_historical(location: Location) -> None:
    """Проверяет получение дневных и почасовых исторических данных."""
    client = Mock()

    client.get_historical_daily.return_value = {
        'daily': {
            'time': ['2026-10-01'],
            'temperature_2m_max': [35.0],
        },
    }
    client.get_historical_hourly.return_value = {
        'hourly': {
            'time': ['2026-10-01T00:00'],
            'temperature_2m': [28.5],
        },
    }

    extractor = WeatherExtractor(client)
    start_date = date(2026, 10, 1)
    end_date = date(2026, 10, 2)

    result = extractor.extract_historical(location, start_date, end_date)

    # Проверяем вызовы API-клиента и возвращённые данные.
    client.get_historical_daily.assert_called_once_with(
        location,
        start_date,
        end_date,
    )
    client.get_historical_hourly.assert_called_once_with(
        location,
        start_date,
        end_date,
    )

    assert result['location'] == location
    assert result['daily']['temperature_2m_max'] == [35.0]
    assert result['hourly']['temperature_2m'] == [28.5]


def test_extract_historical_invalid_dates(location: Location) -> None:
    """Проверяет отказ от запросов при некорректном периоде."""
    client = Mock()
    extractor = WeatherExtractor(client)

    with pytest.raises(
        ValueError,
        match='Начальная дата не может быть позже конечной',
    ):
        extractor.extract_historical(
            location,
            date(2026, 10, 10),
            date(2026, 10, 1),
        )

    # При ошибке в датах API-клиент не должен вызываться.
    client.get_historical_daily.assert_not_called()
    client.get_historical_hourly.assert_not_called()


def test_extract_forecast(location: Location) -> None:
    """Проверяет получение дневного, почасового и ECMWF-прогноза."""
    client = Mock()

    client.get_forecast_daily.return_value = {
        'daily': {
            'time': ['2026-10-28'],
            'temperature_2m_max': [33.0],
        },
    }
    client.get_forecast_hourly.return_value = {
        'hourly': {
            'time': ['2026-10-28T00:00'],
            'temperature_2m': [28.5],
        },
    }
    client.get_ecmwf_hourly.return_value = {
        'hourly': {
            'time': ['2026-10-29T00:00'],
            'precipitation_type': [1.0],
        },
    }

    extractor = WeatherExtractor(client)

    result = extractor.extract_forecast(location, forecast_days=7)

    # Проверяем вызовы API-клиента и возвращённые данные.
    client.get_forecast_daily.assert_called_once_with(location, 7)
    client.get_forecast_hourly.assert_called_once_with(location, 7)
    client.get_ecmwf_hourly.assert_called_once_with(location, 7)

    assert result['location'] == location
    assert result['daily']['temperature_2m_max'] == [33.0]
    assert result['hourly']['temperature_2m'] == [28.5]
    assert result['ecmwf_hourly']['precipitation_type'] == [1.0]

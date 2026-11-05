"""Тесты клиента Open-Meteo без реальных сетевых запросов."""

from datetime import date

import httpx
import pytest

from weather_analytics.api import OpenMeteoClient
from weather_analytics.api.constants import (
    FORECAST_DAILY,
    FORECAST_HOURLY,
)
from weather_analytics.models.weather import Location


@pytest.fixture
def location() -> Location:
    """Создаёт тестовую локацию Лимасол."""
    return Location(
        name='Limassol',
        country='Cyprus',
        latitude=34.68406,
        longitude=33.03794,
        timezone='Asia/Nicosia',
    )


@pytest.fixture
def dubai() -> Location:
    """Создаёт тестовую локацию Дубай."""
    return Location(
        name='Dubai',
        country='United Arab Emirates',
        latitude=25.07725,
        longitude=55.30927,
        timezone='Asia/Dubai',
    )


def test_search_location() -> None:
    """Проверяет преобразование ответа Geocoding API."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Возвращает тестовый результат поиска города."""
        assert request.url.params['name'] == 'Limassol'

        return httpx.Response(
            200,
            json={
                'results': [
                    {
                        'name': 'Limassol',
                        'country': 'Cyprus',
                        'latitude': 34.68406,
                        'longitude': 33.03794,
                        'timezone': 'Asia/Nicosia',
                    },
                ],
            },
        )

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        result = client.search_location('Limassol')

    assert result is not None
    assert result.name == 'Limassol'
    assert result.country == 'Cyprus'
    assert result.latitude == 34.68406


def test_search_location_not_found() -> None:
    """Проверяет отсутствие результатов геокодирования."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Возвращает пустой ответ геокодирования."""
        return httpx.Response(200, json={'generationtime_ms': 0.1})

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        result = client.search_location('UnknownCity')

    assert result is None


def test_get_current_weather(location: Location) -> None:
    """Проверяет получение текущих погодных показателей."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Возвращает тестовые показатели текущей погоды."""
        assert request.url.params['latitude'] == '34.68406'

        return httpx.Response(
            200,
            json={
                'current': {
                    'time': '2026-10-26T13:15',
                    'temperature_2m': 24.7,
                    'relative_humidity_2m': 61,
                    'wind_speed_10m': 8.2,
                },
            },
        )

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        weather = client.get_current_weather(location)

    assert weather.temperature == 24.7
    assert weather.humidity == 61
    assert weather.wind_speed == 8.2
    assert weather.location.name == 'Limassol'


def test_http_error() -> None:
    """Проверяет обработку ошибки внешнего API."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Имитирует HTTP-ошибку сервера."""
        return httpx.Response(503)

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.search_location('Limassol')


@pytest.mark.parametrize(
    ('method_name', 'data_key', 'time_values', 'temperature_values'),
    [
        (
            'get_historical_daily',
            'daily',
            ['2026-10-01', '2026-10-02'],
            [35.0, 34.0],
        ),
        (
            'get_historical_hourly',
            'hourly',
            [1790812800, 1790816400],
            [28.5, 28.1],
        ),
    ],
)
def test_get_historical_success(
    dubai: Location,
    method_name,
    data_key,
    time_values,
    temperature_values,
) -> None:
    """Проверяет запросы и получение исторических данных."""

    temperature_key = (
        'temperature_2m_max'
        if data_key == 'daily'
        else 'temperature_2m'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        """Проверяет параметры запроса и возвращает историю."""
        assert request.url.path == '/v1/archive'
        assert request.url.params['start_date'] == '2026-10-01'
        assert request.url.params['end_date'] == '2026-10-02'
        assert request.url.params['timezone'] == 'Asia/Dubai'

        if data_key == 'hourly':
            assert request.url.params['timeformat'] == 'unixtime'
            assert 'temperature_2m' in request.url.params.get_list('hourly')

        return httpx.Response(
            200,
            json={
                data_key: {
                    'time': time_values,
                    temperature_key: temperature_values,
                },
            },
        )

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        result = getattr(client, method_name)(
            dubai,
            date(2026, 10, 1),
            date(2026, 10, 2),
        )

    assert result[data_key]['time'] == time_values
    assert result[data_key][temperature_key] == temperature_values


@pytest.mark.parametrize(
    ('method_name', 'data_key', 'expected_message'),
    [
        (
            'get_historical_daily',
            'daily',
            'отсутствуют ежедневные данные',
        ),
        (
            'get_historical_hourly',
            'hourly',
            'отсутствуют почасовые данные',
        ),
    ],
)
def test_get_historical_missing_data(
    dubai: Location,
    method_name,
    data_key,
    expected_message,
) -> None:
    """Проверяет отсутствие обязательного блока исторических данных."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Возвращает ответ без исторических показателей."""
        return httpx.Response(200, json={'latitude': 25.0})

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match=expected_message):
            getattr(client, method_name)(
                dubai,
                date(2026, 10, 1),
                date(2026, 10, 2),
            )


@pytest.mark.parametrize(
    'method_name',
    ['get_historical_daily', 'get_historical_hourly'],
)
def test_get_historical_invalid_dates(
    dubai: Location,
    method_name,
) -> None:
    """Проверяет отказ от загрузки при неправильном периоде."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Запрещает HTTP-запрос при ошибке в датах."""
        pytest.fail('HTTP-запрос не должен выполняться')

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            ValueError,
            match='Начальная дата не может быть позже конечной',
        ):
            getattr(client, method_name)(
                dubai,
                date(2026, 10, 10),
                date(2026, 10, 1),
            )


@pytest.mark.parametrize(
    ('method_name', 'data_key', 'columns', 'temperature_key'),
    [
        (
            'get_forecast_daily',
            'daily',
            FORECAST_DAILY,
            'temperature_2m_max',
        ),
        (
            'get_forecast_hourly',
            'hourly',
            FORECAST_HOURLY,
            'temperature_2m',
        ),
    ],
)
def test_get_forecast_success(
    dubai: Location,
    method_name,
    data_key,
    columns,
    temperature_key,
) -> None:
    """Проверяет параметры запроса и получение прогноза."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Проверяет запрос и возвращает тестовый прогноз."""
        assert request.url.path == '/v1/forecast'
        assert request.url.params['latitude'] == '25.07725'
        assert request.url.params['longitude'] == '55.30927'
        assert request.url.params['forecast_days'] == '7'
        assert request.url.params['timezone'] == 'Asia/Dubai'
        assert request.url.params.get_list(data_key) == list(columns)

        return httpx.Response(
            200,
            json={
                data_key: {
                    'time': ['2026-10-28', '2026-10-29'],
                    temperature_key: [33.0, 32.5],
                },
            },
        )

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        result = getattr(client, method_name)(dubai, forecast_days=7)

    assert result[data_key][temperature_key] == [33.0, 32.5]


@pytest.mark.parametrize(
    'method_name',
    ['get_forecast_daily', 'get_forecast_hourly'],
)
@pytest.mark.parametrize('forecast_days', [0, 17])
def test_get_forecast_invalid_days(
    dubai: Location,
    method_name,
    forecast_days,
) -> None:
    """Проверяет границы допустимого периода прогноза."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Запрещает HTTP-запрос при неправильном периоде."""
        pytest.fail('HTTP-запрос не должен выполняться')

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            ValueError,
            match='Количество дней прогноза должно быть от 1 до 16',
        ):
            getattr(client, method_name)(dubai, forecast_days)


@pytest.mark.parametrize(
    ('method_name', 'expected_message'),
    [
        ('get_forecast_daily', 'отсутствуют ежедневные прогнозы'),
        ('get_forecast_hourly', 'отсутствуют почасовые прогнозы'),
    ],
)
def test_get_forecast_missing_data(
    dubai: Location,
    method_name,
    expected_message,
) -> None:
    """Проверяет отсутствие обязательного блока прогноза."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Возвращает ответ без прогнозных показателей."""
        return httpx.Response(200, json={'latitude': 25.0})

    with OpenMeteoClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match=expected_message):
            getattr(client, method_name)(dubai)

"""HTTP-транспорт и единый публичный клиент Open-Meteo.

Модуль объединяет сетевой транспорт, геокодирование и получение
погодных данных через композицию классов.

OpenMeteoHTTPClient отвечает за HTTP-соединения, выполнение
запросов и обработку ошибок внешнего API.

OpenMeteoClient предоставляет единый публичный интерфейс
для Telegram-бота Stormy и ETL-процессов.
"""

from datetime import date
from typing import Any

import httpx

from weather_analytics.api.constants import (
    DEFAULT_LANGUAGE,
    DEFAULT_RESULT_COUNT,
)
from weather_analytics.api.geocoding import OpenMeteoGeocoding
from weather_analytics.api.weather import OpenMeteoWeather
from weather_analytics.config import get_settings
from weather_analytics.models.weather import CurrentWeather, Location


class OpenMeteoHTTPClient:
    """Управляет HTTP-соединениями и запросами к Open-Meteo."""

    def __init__(
        self,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Создаёт HTTP-клиент с настройками приложения.

        Args:
            timeout: Таймаут запросов в секундах. Если не указан,
                используется значение из конфигурации.
            transport: Необязательный транспорт HTTPX для тестирования.
        """
        settings = get_settings()

        # Адреса конечных точек получаем из общей конфигурации.
        # Они используются только внутренними компонентами API.
        self.geocoding_url = settings.geocoding_url
        self.forecast_url = settings.forecast_url
        self.archive_url = settings.archive_url
        self.ecmwf_url = settings.ecmwf_url

        # Один HTTP-клиент обеспечивает повторное использование
        # соединений при последовательных запросах.
        self._client = httpx.Client(
            timeout=(
                timeout
                if timeout is not None
                else settings.http_timeout
            ),
            transport=transport,
        )

    def __enter__(self) -> 'OpenMeteoHTTPClient':
        """Возвращает HTTP-клиент при входе в контекстный менеджер."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        """Закрывает HTTP-соединения при выходе из контекстного менеджера."""
        self.close()

    def close(self) -> None:
        """Закрывает HTTP-клиент и освобождает сетевые ресурсы."""
        self._client.close()

    def get(
        self,
        url: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Выполняет GET-запрос и проверяет ответ Open-Meteo.

        Args:
            url: Адрес конечной точки Open-Meteo.
            params: Параметры HTTP-запроса.

        Returns:
            JSON-ответ API в виде словаря.

        Raises:
            httpx.HTTPStatusError: Если сервер вернул ошибочный
                HTTP-статус.
            httpx.RequestError: Если произошла сетевая ошибка.
            ValueError: Если ответ имеет некорректный формат
                или содержит сообщение об ошибке API.
        """
        response = self._client.get(
            url,
            params=params,
        )
        response.raise_for_status()

        data = response.json()

        # Все используемые конечные точки Open-Meteo
        # должны возвращать JSON-объект верхнего уровня.
        if not isinstance(data, dict):
            raise ValueError(
                'Некорректный формат ответа Open-Meteo'
            )

        # Некоторые ошибки Open-Meteo передаются в JSON
        # через поля error и reason.
        if data.get('error'):
            raise ValueError(
                f'Ошибка Open-Meteo: '
                f'{data.get("reason", "неизвестная ошибка")}'
            )

        return data


class OpenMeteoClient:
    """Предоставляет единый интерфейс для работы с Open-Meteo.

    Объединяет компоненты геокодирования и получения погоды
    через композицию.

    Все компоненты используют один экземпляр
    OpenMeteoHTTPClient.
    """

    def __init__(
        self,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Создаёт общий HTTP-клиент и специализированные компоненты.

        Args:
            timeout: Таймаут HTTP-запросов в секундах.
            transport: Необязательный транспорт HTTPX для тестирования.
        """
        # Создаём один транспорт для всех запросов.
        self._http = OpenMeteoHTTPClient(
            timeout=timeout,
            transport=transport,
        )

        # Каждый компонент отвечает за свою предметную область.
        self._geocoding = OpenMeteoGeocoding(self._http)
        self._weather = OpenMeteoWeather(self._http)

    def __enter__(self) -> 'OpenMeteoClient':
        """Возвращает клиент при входе в контекстный менеджер."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        """Закрывает соединения при выходе из контекстного менеджера."""
        self.close()

    def close(self) -> None:
        """Закрывает общий HTTP-клиент и освобождает ресурсы."""
        self._http.close()

    # ========================================================
    # ГЕОКОДИРОВАНИЕ
    # ========================================================

    def find_locations(
        self,
        city: str,
        language: str = DEFAULT_LANGUAGE,
        count: int = DEFAULT_RESULT_COUNT,
    ) -> list[dict[str, Any]]:
        """Ищет населённые пункты по названию.

        Args:
            city: Название населённого пункта.
            language: Язык результатов геокодирования.
            count: Максимальное количество совпадений.

        Returns:
            Список найденных географических объектов.
        """
        return self._geocoding.find_locations(
            city=city,
            language=language,
            count=count,
        )

    def search_location(
        self,
        city: str,
    ) -> Location | None:
        """Находит населённый пункт и возвращает модель Location.

        Args:
            city: Название населённого пункта.

        Returns:
            Модель Location или None, если совпадений нет.
        """
        return self._geocoding.search_location(city)

    # ========================================================
    # ТЕКУЩАЯ ПОГОДА
    # ========================================================

    def get_current_weather(
        self,
        location: Location,
    ) -> CurrentWeather:
        """Получает текущую погоду в модели приложения.

        Args:
            location: Географическая локация.

        Returns:
            Модель CurrentWeather.
        """
        return self._weather.get_current_weather(location)

    def get_bot_current(
        self,
        city: dict[str, Any],
    ) -> dict[str, Any]:
        """Получает текущие погодные показатели для Stormy.

        Args:
            city: Данные выбранного населённого пункта.

        Returns:
            Ответ API с разделом current.
        """
        return self._weather.get_bot_current(city)

    # ========================================================
    # ИСТОРИЧЕСКИЕ ДАННЫЕ
    # ========================================================

    def get_historical_daily(
        self,
        location: Location,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Получает суточные исторические показатели.

        Args:
            location: Географическая локация.
            start_date: Начало исторического периода.
            end_date: Конец исторического периода.

        Returns:
            Ответ API с разделом daily.
        """
        return self._weather.get_historical_daily(
            location,
            start_date,
            end_date,
        )

    def get_historical_hourly(
        self,
        location: Location,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Получает почасовые исторические показатели.

        Args:
            location: Географическая локация.
            start_date: Начало исторического периода.
            end_date: Конец исторического периода.

        Returns:
            Ответ API с разделом hourly.
        """
        return self._weather.get_historical_hourly(
            location,
            start_date,
            end_date,
        )

    # ========================================================
    # ПРОГНОЗЫ
    # ========================================================

    def get_forecast_daily(
        self,
        location: Location,
        forecast_days: int = 7,
    ) -> dict[str, Any]:
        """Получает суточный прогноз погоды.

        Args:
            location: Географическая локация.
            forecast_days: Количество дней прогноза.

        Returns:
            Ответ API с разделом daily.
        """
        return self._weather.get_forecast_daily(
            location,
            forecast_days,
        )

    def get_forecast_hourly(
        self,
        location: Location,
        forecast_days: int = 7,
    ) -> dict[str, Any]:
        """Получает почасовой прогноз погоды.

        Args:
            location: Географическая локация.
            forecast_days: Количество дней прогноза.

        Returns:
            Ответ API с разделом hourly.
        """
        return self._weather.get_forecast_hourly(
            location,
            forecast_days,
        )

    def get_ecmwf_hourly(
        self,
        location: Location,
        forecast_days: int = 7,
    ) -> dict[str, Any]:
        """Получает специализированные почасовые показатели ECMWF.

        Args:
            location: Географическая локация.
            forecast_days: Количество дней прогноза.

        Returns:
            Ответ API ECMWF с разделом hourly.
        """
        return self._weather.get_ecmwf_hourly(
            location,
            forecast_days,
        )

    # ========================================================
    # ПОГОДНЫЕ ДАННЫЕ ДЛЯ STORMY
    # ========================================================

    def get_bot_period(
        self,
        city: dict[str, Any],
        start_date: date,
        end_date: date,
        historical: bool = False,
    ) -> dict[str, Any]:
        """Получает исторические или прогнозные данные для Stormy.

        Args:
            city: Данные выбранного населённого пункта.
            start_date: Начало периода.
            end_date: Конец периода.
            historical: Признак исторического периода.

        Returns:
            Ответ API с суточными и почасовыми показателями.
        """
        return self._weather.get_bot_period(
            city=city,
            start_date=start_date,
            end_date=end_date,
            historical=historical,
        )

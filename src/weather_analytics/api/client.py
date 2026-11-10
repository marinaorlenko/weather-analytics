"""HTTP-транспорт и единый публичный клиент Open-Meteo.

Модуль объединяет сетевой транспорт, геокодирование и получение
погодных данных через композицию классов.

HTTP-транспорт обрабатывает временные ошибки API, повторные
попытки и ограничение частоты исторических запросов.
"""

import logging
import time
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from threading import Lock
from typing import Any

import httpx

from weather_analytics.api.constants import (
    DEFAULT_FORECAST_DAYS,
    DEFAULT_LANGUAGE,
    DEFAULT_RESULT_COUNT,
    HTTP_INITIAL_ATTEMPTS,
    HTTP_MAX_RETRIES,
    HTTP_RATE_LIMIT_INITIAL_TIME,
    HTTP_RETRY_BACKOFF_FACTOR,
    HTTP_RETRY_BASE_DELAY,
    HTTP_RETRY_MAX_DELAY,
    RETRYABLE_HTTP_STATUSES,
)
from weather_analytics.api.geocoding import OpenMeteoGeocoding
from weather_analytics.api.weather import OpenMeteoWeather
from weather_analytics.config import get_settings
from weather_analytics.models.weather import CurrentWeather, Location

logger = logging.getLogger(__name__)


class RequestRateLimiter:
    """Ограничивает частоту последовательных HTTP-запросов."""

    def __init__(self, interval: float) -> None:
        """Создаёт ограничитель с заданным интервалом в секундах."""
        self._interval = interval
        self._lock = Lock()
        self._next_request = HTTP_RATE_LIMIT_INITIAL_TIME

    def wait(self) -> None:
        """Ожидает наступления разрешённого времени запроса."""
        if self._interval <= 0:
            return

        # Блокировка не позволяет потокам одновременно
        # пройти проверку времени следующего запроса.
        with self._lock:
            remaining = self._next_request - time.monotonic()

            if remaining > 0:
                time.sleep(remaining)

            self._next_request = time.monotonic() + self._interval


class OpenMeteoHTTPClient:
    """Управляет HTTP-соединениями и запросами к Open-Meteo."""

    def __init__(
        self,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
        rate_limiter: RequestRateLimiter | None = None,
    ) -> None:
        """Создаёт HTTP-клиент с настройками приложения.

        Args:
            timeout: Необязательный таймаут HTTP-запросов.
            transport: Транспорт HTTPX для тестирования.
            rate_limiter: Общий ограничитель исторических запросов.
        """
        settings = get_settings()

        self.geocoding_url = settings.geocoding_url
        self.forecast_url = settings.forecast_url
        self.archive_url = settings.archive_url
        self.ecmwf_url = settings.ecmwf_url

        self._rate_limiter = (
            rate_limiter
            if rate_limiter is not None
            else RequestRateLimiter(settings.etl_request_delay)
        )

        self._client = httpx.Client(
            timeout=(timeout if timeout is not None else settings.http_timeout),
            transport=transport,
        )

    def __enter__(self) -> 'OpenMeteoHTTPClient':
        """Возвращает клиент при входе в контекстный менеджер."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        """Закрывает соединения при выходе из контекста."""
        self.close()

    def close(self) -> None:
        """Закрывает HTTP-клиент и освобождает ресурсы."""
        self._client.close()

    @staticmethod
    def _retry_delay(
        attempt: int,
        response: httpx.Response | None = None,
    ) -> float:
        """Вычисляет паузу перед повторным HTTP-запросом.

        Учитывает экспоненциальную задержку и Retry-After,
        не превышая максимальное разрешённое время ожидания.
        """
        delay = min(
            HTTP_RETRY_BASE_DELAY * HTTP_RETRY_BACKOFF_FACTOR**attempt,
            HTTP_RETRY_MAX_DELAY,
        )

        if response is None:
            return delay

        retry_after = response.headers.get('Retry-After')

        if not retry_after:
            return delay

        try:
            requested_delay = float(retry_after)
        except ValueError:
            # Retry-After может содержать HTTP-дату.
            try:
                retry_date = parsedate_to_datetime(retry_after)

                if retry_date.tzinfo is None:
                    retry_date = retry_date.replace(tzinfo=UTC)

                requested_delay = (
                    retry_date - datetime.now(UTC)
                ).total_seconds()

            except (TypeError, ValueError, OverflowError):
                return delay

        return min(
            max(delay, requested_delay),
            HTTP_RETRY_MAX_DELAY,
        )

    def get(
        self,
        url: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Выполняет GET-запрос с обработкой временных ошибок.

        Args:
            url: Адрес конечной точки Open-Meteo.
            params: Параметры запроса.

        Returns:
            JSON-ответ API в виде словаря.

        Raises:
            httpx.HTTPStatusError: При ошибочном HTTP-статусе.
            httpx.RequestError: При сетевой ошибке.
            ValueError: При некорректном ответе Open-Meteo.
        """
        for attempt in range(HTTP_MAX_RETRIES + HTTP_INITIAL_ATTEMPTS):
            # Ограничение скорости применяется только
            # к историческому API, не задерживая прогнозы.
            if url == self.archive_url:
                self._rate_limiter.wait()

            try:
                response = self._client.get(
                    url,
                    params=params,
                )

                if (
                    response.status_code in RETRYABLE_HTTP_STATUSES
                    and attempt < HTTP_MAX_RETRIES
                ):
                    delay = self._retry_delay(
                        attempt,
                        response,
                    )

                    logger.warning(
                        'Open-Meteo: HTTP %s, повтор %s/%s через %.1f сек.',
                        response.status_code,
                        attempt + HTTP_INITIAL_ATTEMPTS,
                        HTTP_MAX_RETRIES,
                        delay,
                    )

                    time.sleep(delay)
                    continue

                response.raise_for_status()

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
            ) as error:
                if attempt >= HTTP_MAX_RETRIES:
                    raise

                delay = self._retry_delay(attempt)

                logger.warning(
                    'Open-Meteo: %s, повтор %s/%s через %.1f сек.',
                    type(error).__name__,
                    attempt + HTTP_INITIAL_ATTEMPTS,
                    HTTP_MAX_RETRIES,
                    delay,
                )

                time.sleep(delay)
                continue

            data = response.json()

            if not isinstance(data, dict):
                raise ValueError('Некорректный формат ответа Open-Meteo')

            if data.get('error'):
                raise ValueError(
                    f'Ошибка Open-Meteo: {data.get("reason", "неизвестная ошибка")}'
                )

            return data

        raise RuntimeError('Не удалось завершить запрос Open-Meteo')


class OpenMeteoClient:
    """Предоставляет единый интерфейс для работы с Open-Meteo.

    Объединяет геокодирование и получение погодных данных
    через композицию специализированных компонентов.
    """

    def __init__(
        self,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
        rate_limiter: RequestRateLimiter | None = None,
    ) -> None:
        """Создаёт HTTP-клиент и компоненты Open-Meteo."""
        self._http = OpenMeteoHTTPClient(
            timeout=timeout,
            transport=transport,
            rate_limiter=rate_limiter,
        )

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
        """Закрывает соединения при выходе из контекста."""
        self.close()

    def close(self) -> None:
        """Закрывает HTTP-соединения."""
        self._http.close()

    def find_locations(
        self,
        city: str,
        language: str = DEFAULT_LANGUAGE,
        count: int = DEFAULT_RESULT_COUNT,
    ) -> list[dict[str, Any]]:
        """Ищет населённые пункты по названию."""
        return self._geocoding.find_locations(
            city=city,
            language=language,
            count=count,
        )

    def search_location(
        self,
        city: str,
    ) -> Location | None:
        """Находит населённый пункт и возвращает модель Location."""
        return self._geocoding.search_location(city)

    def get_current_weather(
        self,
        location: Location,
    ) -> CurrentWeather:
        """Получает текущую погоду в модели приложения."""
        return self._weather.get_current_weather(location)

    def get_bot_current(
        self,
        city: dict[str, Any],
    ) -> dict[str, Any]:
        """Получает текущие погодные показатели для Stormy."""
        return self._weather.get_bot_current(city)

    def get_historical_daily(
        self,
        location: Location,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Получает суточные исторические показатели."""
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
        """Получает почасовые исторические показатели."""
        return self._weather.get_historical_hourly(
            location,
            start_date,
            end_date,
        )

    def get_forecast_daily(
        self,
        location: Location,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
    ) -> dict[str, Any]:
        """Получает суточный прогноз погоды."""
        return self._weather.get_forecast_daily(
            location,
            forecast_days,
        )

    def get_forecast_hourly(
        self,
        location: Location,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
    ) -> dict[str, Any]:
        """Получает почасовой прогноз погоды."""
        return self._weather.get_forecast_hourly(
            location,
            forecast_days,
        )

    def get_ecmwf_hourly(
        self,
        location: Location,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
    ) -> dict[str, Any]:
        """Получает специализированный почасовой прогноз ECMWF."""
        return self._weather.get_ecmwf_hourly(
            location,
            forecast_days,
        )

    def get_bot_period(
        self,
        city: dict[str, Any],
        start_date: date,
        end_date: date,
        historical: bool = False,
    ) -> dict[str, Any]:
        """Получает исторические или прогнозные данные для Stormy."""
        return self._weather.get_bot_period(
            city=city,
            start_date=start_date,
            end_date=end_date,
            historical=historical,
        )

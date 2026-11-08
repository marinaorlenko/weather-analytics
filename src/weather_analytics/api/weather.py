"""Получение погодных данных через API Open-Meteo.

Модуль содержит операции для текущей погоды, исторических
наблюдений, прогнозов и специализированных данных ECMWF.

HTTP-запросы выполняет OpenMeteoHTTPClient.
Параметры источника централизованы в модуле constants.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from weather_analytics.api.constants import (
    BOT_CURRENT,
    BOT_DAILY,
    BOT_FORECAST_DAILY_EXTRA,
    BOT_FORECAST_HOURLY_EXTRA,
    BOT_HOURLY,
    CURRENT_WEATHER_FIELDS,
    DEFAULT_FORECAST_DAYS,
    ECMWF_HOURLY,
    FORECAST_DAILY,
    FORECAST_HOURLY,
    HISTORICAL_DAILY,
    HISTORICAL_HOURLY,
    MAX_ECMWF_FORECAST_DAYS,
    MAX_FORECAST_DAYS,
)
from weather_analytics.models.weather import CurrentWeather, Location

if TYPE_CHECKING:
    from weather_analytics.api.client import OpenMeteoHTTPClient


class OpenMeteoWeather:
    """Предоставляет операции получения погодных данных Open-Meteo."""

    def __init__(self, client: OpenMeteoHTTPClient) -> None:
        """Принимает HTTP-клиент для выполнения запросов.

        Args:
            client: Общий HTTP-клиент Open-Meteo.
        """
        # Используем существующее соединение, не создавая нового.
        # Жизненным циклом HTTP-клиента управляет внешний слой.
        self._client = client

    @staticmethod
    def _location_params(
        location: Location | dict[str, Any],
    ) -> dict[str, Any]:
        """Формирует координаты и часовой пояс для запроса.

        Args:
            location: Модель Location или словарь геокодирования.

        Returns:
            Параметры местоположения для Open-Meteo.
        """
        # ETL работает с Location, а Stormy пока использует
        # словари геокодирования. Поддерживаем оба представления.
        if isinstance(location, Location):
            return {
                'latitude': location.latitude,
                'longitude': location.longitude,
                'timezone': location.timezone,
            }

        return {
            'latitude': location['latitude'],
            'longitude': location['longitude'],
            'timezone': location.get('timezone') or 'UTC',
        }

    @staticmethod
    def _validate_date_range(
        start_date: date,
        end_date: date,
    ) -> None:
        """Проверяет правильность диапазона дат.

        Args:
            start_date: Начало периода.
            end_date: Конец периода.

        Raises:
            ValueError: Если начальная дата позже конечной.
        """
        if start_date > end_date:
            raise ValueError('Начальная дата не может быть позже конечной')

    @staticmethod
    def _validate_forecast_days(
        forecast_days: int,
        max_days: int,
        source: str = '',
    ) -> None:
        """Проверяет допустимую продолжительность прогноза.

        Args:
            forecast_days: Запрошенное количество дней.
            max_days: Максимально допустимое количество дней.
            source: Название источника для сообщения об ошибке.

        Raises:
            ValueError: Если количество дней недопустимо.
        """
        if not 1 <= forecast_days <= max_days:
            name = f' {source}' if source else ''
            raise ValueError(
                f'Количество дней прогноза{name} должно быть от 1 до {max_days}'
            )

    @staticmethod
    def _require_section(
        data: dict[str, Any],
        section: str,
        message: str,
    ) -> dict[str, Any]:
        """Проверяет наличие обязательного раздела в ответе API.

        Args:
            data: Ответ Open-Meteo.
            section: Название обязательного раздела.
            message: Сообщение об ошибке.

        Returns:
            Исходный ответ API.

        Raises:
            ValueError: Если обязательный раздел отсутствует.
        """
        if section not in data:
            raise ValueError(message)

        return data

    def get_current_weather(
        self,
        location: Location,
    ) -> CurrentWeather:
        """Получает текущую погоду в модели приложения.

        Args:
            location: Географическая локация.

        Returns:
            Модель CurrentWeather с текущими показателями.
        """
        params = {
            **self._location_params(location),
            'current': CURRENT_WEATHER_FIELDS,
        }

        data = self._client.get(
            self._client.forecast_url,
            params,
        )
        current = data['current']

        # Преобразуем ответ API в существующую модель приложения.
        return CurrentWeather(
            location=location,
            observed_at=current['time'],
            temperature=current['temperature_2m'],
            humidity=current['relative_humidity_2m'],
            wind_speed=current['wind_speed_10m'],
        )

    def get_historical_daily(
        self,
        location: Location,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Получает расширенные суточные исторические показатели.

        Args:
            location: Географическая локация.
            start_date: Начало исторического периода.
            end_date: Конец исторического периода.

        Returns:
            Ответ Open-Meteo с разделом daily.
        """
        self._validate_date_range(start_date, end_date)

        params = {
            **self._location_params(location),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'daily': HISTORICAL_DAILY,
        }

        data = self._client.get(
            self._client.archive_url,
            params,
        )

        return self._require_section(
            data,
            'daily',
            'В ответе Open-Meteo отсутствуют ежедневные данные',
        )

    def get_historical_hourly(
        self,
        location: Location,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Получает расширенные почасовые исторические показатели.

        Args:
            location: Географическая локация.
            start_date: Начало исторического периода.
            end_date: Конец исторического периода.

        Returns:
            Ответ Open-Meteo с разделом hourly.
        """
        self._validate_date_range(start_date, end_date)

        params = {
            **self._location_params(location),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'hourly': HISTORICAL_HOURLY,
            'timeformat': 'unixtime',
        }

        data = self._client.get(
            self._client.archive_url,
            params,
        )

        return self._require_section(
            data,
            'hourly',
            'В ответе Open-Meteo отсутствуют почасовые данные',
        )

    def get_forecast_daily(
        self,
        location: Location,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
    ) -> dict[str, Any]:
        """Получает расширенный суточный прогноз погоды.

        Args:
            location: Географическая локация.
            forecast_days: Количество дней прогноза.

        Returns:
            Ответ Open-Meteo с разделом daily.
        """
        self._validate_forecast_days(
            forecast_days,
            MAX_FORECAST_DAYS,
        )

        params = {
            **self._location_params(location),
            'daily': FORECAST_DAILY,
            'forecast_days': forecast_days,
        }

        data = self._client.get(
            self._client.forecast_url,
            params,
        )

        return self._require_section(
            data,
            'daily',
            'В ответе Open-Meteo отсутствуют ежедневные прогнозы',
        )

    def get_forecast_hourly(
        self,
        location: Location,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
    ) -> dict[str, Any]:
        """Получает расширенный почасовой прогноз погоды.

        Args:
            location: Географическая локация.
            forecast_days: Количество дней прогноза.

        Returns:
            Ответ Open-Meteo с разделом hourly.
        """
        self._validate_forecast_days(
            forecast_days,
            MAX_FORECAST_DAYS,
        )

        params = {
            **self._location_params(location),
            'hourly': FORECAST_HOURLY,
            'forecast_days': forecast_days,
            'timeformat': 'unixtime',
        }

        data = self._client.get(
            self._client.forecast_url,
            params,
        )

        return self._require_section(
            data,
            'hourly',
            'В ответе Open-Meteo отсутствуют почасовые прогнозы',
        )

    def get_ecmwf_hourly(
        self,
        location: Location,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
    ) -> dict[str, Any]:
        """Получает специализированные почасовые показатели ECMWF.

        Args:
            location: Географическая локация.
            forecast_days: Количество дней прогноза.

        Returns:
            Ответ ECMWF с разделом hourly.
        """
        self._validate_forecast_days(
            forecast_days,
            MAX_ECMWF_FORECAST_DAYS,
            source='ECMWF',
        )

        params = {
            **self._location_params(location),
            'hourly': ECMWF_HOURLY,
            'forecast_days': forecast_days,
            'timeformat': 'unixtime',
        }

        data = self._client.get(
            self._client.ecmwf_url,
            params,
        )

        return self._require_section(
            data,
            'hourly',
            'В ответе ECMWF отсутствуют почасовые данные',
        )

    def get_bot_current(
        self,
        city: dict[str, Any],
    ) -> dict[str, Any]:
        """Получает текущие показатели для Telegram-бота Stormy.

        Args:
            city: Данные выбранного населённого пункта.

        Returns:
            Ответ Open-Meteo с разделом current.
        """
        params = {
            **self._location_params(city),
            'current': BOT_CURRENT,
        }

        data = self._client.get(
            self._client.forecast_url,
            params,
        )

        return self._require_section(
            data,
            'current',
            'В ответе Open-Meteo отсутствуют текущие данные',
        )

    def get_bot_period(
        self,
        city: dict[str, Any],
        start_date: date,
        end_date: date,
        historical: bool = False,
    ) -> dict[str, Any]:
        """Получает погодные данные за период для Stormy.

        Args:
            city: Данные выбранного населённого пункта.
            start_date: Начало периода.
            end_date: Конец периода.
            historical: Признак исторического периода.

        Returns:
            Ответ Open-Meteo с суточными и почасовыми данными.
        """
        self._validate_date_range(start_date, end_date)

        # Формируем отдельные наборы полей для архива и прогноза.
        # Кортежи из constants.py при этом остаются неизменными.
        daily: tuple[str, ...] = BOT_DAILY
        hourly: tuple[str, ...] = BOT_HOURLY

        if not historical:
            daily += BOT_FORECAST_DAILY_EXTRA
            hourly += BOT_FORECAST_HOURLY_EXTRA

        params = {
            **self._location_params(city),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'daily': daily,
            'hourly': hourly,
        }

        # Выбираем конечную точку API по типу периода.
        url = self._client.archive_url if historical else self._client.forecast_url

        data = self._client.get(url, params)

        self._require_section(
            data,
            'daily',
            'В ответе Open-Meteo отсутствуют суточные данные',
        )

        return self._require_section(
            data,
            'hourly',
            'В ответе Open-Meteo отсутствуют почасовые данные',
        )

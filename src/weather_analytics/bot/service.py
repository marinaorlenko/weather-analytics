"""Получение погодных данных для Telegram-бота Stormy.

Определяет локальную дату выбранного города, проверяет
доступность запрошенного периода и получает данные
через OpenMeteoClient.
"""

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from weather_analytics.api import OpenMeteoClient
from weather_analytics.bot.constants import (
    MIN_HISTORICAL_DATE,
    SATURDAY_WEEKDAY,
    SUNDAY_WEEKDAY,
    WEEK_FORECAST_DAYS,
)

# from weather_analytics.bot.city_search import CitySearchService
from weather_analytics.bot.parser import WeatherQuery, resolve_date


class WeatherService:
    """Обрабатывает погодные запросы для выбранного города."""

    def __init__(self, client: OpenMeteoClient) -> None:
        """Инициализирует сервис с общим API-клиентом.

        Args:
            client: Клиент для получения данных Open-Meteo.
        """
        self.client = client

    # def find_cities(
    #     self,
    #     name: str,
    #     language: str,
    # ) -> list[dict[str, Any]]:
    #     """Делегирует поиск городов специализированному сервису.

    #     Временный метод совместимости с telegram_bot.py.
    #     После обновления обработчиков будет удалён.
    #     """
    #     return CitySearchService(self.client).find_cities(
    #         name,
    #         language,
    #     )

    # def suggest_cities(
    #     self,
    #     name: str,
    #     language: str,
    # ) -> list[dict[str, Any]]:
    #     """Делегирует поиск похожих городов.

    #     Временный метод совместимости с telegram_bot.py.
    #     После обновления обработчиков будет удалён.
    #     """
    #     return CitySearchService(self.client).suggest_cities(
    #         name,
    #         language,
    #     )

    def get_weather(
        self,
        city: dict[str, Any],
        query: WeatherQuery,
    ) -> dict[str, Any]:
        """Получает погоду за запрошенный период.

        Даты определяются относительно локального календаря
        выбранного города, а не календаря сервера.

        Args:
            city: Выбранный населённый пункт из геокодера.
            query: Разобранный погодный запрос.

        Returns:
            Данные текущей погоды, одного дня или периода
            в формате, ожидаемом Telegram-ботом.

        Raises:
            ValueError: С кодом year_required, invalid_date,
                future_range, past_range или mixed_range.
        """
        # Часовой пояс берём из результата геокодирования.
        # При его отсутствии используем UTC.
        timezone = city.get('timezone') or 'UTC'
        today = datetime.now(ZoneInfo(timezone)).date()

        if query.period == 'now':
            data = self.client.get_bot_current(city)

            return {
                'kind': 'now',
                'date': today,
                'current': data['current'],
            }

        if query.period == 'week':
            # Семь календарных дней, начиная с сегодняшнего.
            start = today
            end = today + timedelta(days=6)

        elif query.period == 'weekend':
            # Ближайшие выходные. В воскресенье показываем
            # только оставшийся день текущих выходных.
            days_until_saturday = (
                SATURDAY_WEEKDAY - today.weekday()
            ) % WEEK_FORECAST_DAYS

            if today.weekday() == SUNDAY_WEEKDAY:
                start = end = today
            else:
                start = today + timedelta(
                    days=days_until_saturday,
                )
                end = start + timedelta(days=1)

        else:
            # Здесь разрешается конкретная календарная дата.
            # Для неоднозначной даты без года resolve_date()
            # выбрасывает year_required до обращения к API.
            target = resolve_date(query, today)
            start = end = target

        # Максимальная доступная глубина прогноза
        # задаётся общей константой API.
        if end > today + timedelta(days=WEEK_FORECAST_DAYS - 1):
            raise ValueError('future_range')

        # Исторические данные не запрашиваем раньше
        # установленной нижней границы.
        if start < MIN_HISTORICAL_DATE:
            raise ValueError('past_range')

        # Исторический и прогнозный API не объединяются
        # в один запрос на пересекающий границу период.
        if start < today <= end:
            raise ValueError('mixed_range')

        historical = end < today

        # API-клиент самостоятельно выбирает endpoint,
        # набор погодных показателей и параметры запроса.
        data = self.client.get_bot_period(
            city=city,
            start_date=start,
            end_date=end,
            historical=historical,
        )

        return {
            'kind': (
                query.period
                if query.period in ('week', 'weekend')
                else 'day'
            ),
            'date': start,
            'daily': data['daily'],
            'hourly': data.get('hourly') or {},
            'historical': historical,
        }

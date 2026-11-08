"""Геокодирование населённых пунктов через Open-Meteo.

Модуль отвечает за поиск географических объектов, получение
нескольких вариантов совпадений и преобразование ответа
Open-Meteo в модель Location приложения.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from weather_analytics.api.constants import (
    DEFAULT_LANGUAGE,
    DEFAULT_RESULT_COUNT,
    MAX_RESULT_COUNT,
    MIN_CITY_LENGTH,
)
from weather_analytics.models.weather import Location

if TYPE_CHECKING:
    from weather_analytics.api.client import OpenMeteoHTTPClient


class OpenMeteoGeocoding:
    """Предоставляет операции поиска локаций через Open-Meteo."""

    def __init__(self, client: OpenMeteoHTTPClient) -> None:
        """Принимает общий HTTP-клиент для выполнения запросов.

        Args:
            client: HTTP-клиент Open-Meteo, управляющий соединениями.
        """
        # Используем переданный клиент, а не создаём новый.
        # Его жизненным циклом управляет вызывающий код.
        self._client = client

    def find_locations(
        self,
        city: str,
        language: str = DEFAULT_LANGUAGE,
        count: int = DEFAULT_RESULT_COUNT,
    ) -> list[dict[str, Any]]:
        """Ищет населённый пункт и возвращает варианты совпадений.

        Args:
            city: Название населённого пункта.
            language: Язык названий в ответе геокодера.
            count: Максимальное количество результатов поиска.

        Returns:
            Список географических объектов в формате Open-Meteo.

        Raises:
            ValueError: При некорректном названии или количестве результатов.
        """
        city = city.strip()

        # Не отправляем запросы с заведомо некорректными параметрами.
        if len(city) < MIN_CITY_LENGTH:
            raise ValueError(
                f'Название города должно содержать минимум {MIN_CITY_LENGTH} символа'
            )

        if not 1 <= count <= MAX_RESULT_COUNT:
            raise ValueError(
                f'Количество результатов должно быть от 1 до {MAX_RESULT_COUNT}'
            )

        params = {
            'name': city,
            'count': count,
            'language': language,
            'format': 'json',
        }

        data = self._client.get(self._client.geocoding_url, params)

        # При отсутствии совпадений Open-Meteo может не вернуть
        # ключ results вообще. В этом случае возвращаем пустой список.
        return data.get('results') or []

    def search_location(self, city: str) -> Location | None:
        """Возвращает первую найденную локацию в модели приложения.

        Args:
            city: Название населённого пункта.

        Returns:
            Модель Location либо None, если совпадений нет.
        """
        results = self.find_locations(
            city=city,
            language=DEFAULT_LANGUAGE,
            count=1,
        )

        if not results:
            return None

        # Сохраняем прежний принцип выбора: первый результат API.
        # Координаты и часовой пояс валидируются моделью Location.
        item = results[0]

        return Location(
            name=item['name'],
            country=item['country'],
            latitude=item['latitude'],
            longitude=item['longitude'],
            timezone=item['timezone'],
        )

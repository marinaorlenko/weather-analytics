# """Извлечение исторических и прогнозных погодных данных из Open-Meteo.

# Модуль отвечает исключительно за получение данных через API-клиент.
# Преобразование, проверка структуры и сохранение данных выполняются
# другими компонентами ETL-процесса.
# """

# import logging
# from datetime import date
# from typing import Any

# from weather_analytics.api import OpenMeteoClient
# from weather_analytics.api.constants import DEFAULT_FORECAST_DAYS
# from weather_analytics.models.weather import Location


# logger = logging.getLogger(__name__)


# class WeatherExtractor:
#     """Получает погодные данные для последующей обработки в ETL."""

#     def __init__(self, client: OpenMeteoClient) -> None:
#         """Принимает общий клиент Open-Meteo.

#         Args:
#             client: Настроенный API-клиент для получения погодных данных.
#         """
#         self.client = client

#     def extract_historical(
#         self,
#         location: Location,
#         start_date: date,
#         end_date: date,
#     ) -> dict[str, Any]:
#         """Получает суточные и почасовые исторические данные.

#         Args:
#             location: Географическая локация.
#             start_date: Начало исторического периода.
#             end_date: Конец исторического периода.

#         Returns:
#             Словарь с локацией, суточными и почасовыми данными.

#         Raises:
#             ValueError: Если начальная дата позже конечной.
#             httpx.HTTPError: Если запрос к Open-Meteo завершился ошибкой.
#         """
#         if start_date > end_date:
#             raise ValueError(
#                 'Начальная дата не может быть позже конечной'
#             )

#         logger.info(
#             'Загрузка истории: %s (%s — %s)',
#             location.name,
#             start_date,
#             end_date,
#         )

#         # Суточные и почасовые показатели запрашиваются отдельно,
#         # поскольку API-клиент предоставляет специализированные методы.
#         daily = self.client.get_historical_daily(
#             location,
#             start_date,
#             end_date,
#         )

#         hourly = self.client.get_historical_hourly(
#             location,
#             start_date,
#             end_date,
#         )

#         return {
#             'location': location,
#             'daily': daily['daily'],
#             'hourly': hourly['hourly'],
#         }

#     def extract_forecast(
#         self,
#         location: Location,
#         forecast_days: int = DEFAULT_FORECAST_DAYS,
#     ) -> dict[str, Any]:
#         """Получает суточный, почасовой и ECMWF-прогнозы.

#         Args:
#             location: Географическая локация.
#             forecast_days: Количество дней прогнозирования.

#         Returns:
#             Словарь с локацией и тремя наборами прогнозных данных.

#         Raises:
#             ValueError: Если API-клиент отклонил параметры запроса.
#             httpx.HTTPError: Если запрос к Open-Meteo завершился ошибкой.
#         """
#         logger.info(
#             'Загрузка прогноза: %s (%s дней)',
#             location.name,
#             forecast_days,
#         )

#         # Основной прогноз предоставляет суточные и почасовые
#         # показатели, которые обрабатываются независимо.
#         daily = self.client.get_forecast_daily(
#             location,
#             forecast_days,
#         )

#         hourly = self.client.get_forecast_hourly(
#             location,
#             forecast_days,
#         )

#         # ECMWF запрашиваем отдельно: эти показатели
#         # сохраняются в собственной таблице PostgreSQL.
#         ecmwf = self.client.get_ecmwf_hourly(
#             location,
#             forecast_days,
#         )

#         return {
#             'location': location,
#             'daily': daily['daily'],
#             'hourly': hourly['hourly'],
#             'ecmwf_hourly': ecmwf['hourly'],
#         }

"""Извлечение исторических и прогнозных погодных данных из Open-Meteo.

Модуль отвечает исключительно за получение данных через API-клиент.
Преобразование, проверка структуры и сохранение данных выполняются
другими компонентами ETL-процесса.
"""

import logging
from datetime import date
from typing import Any

from weather_analytics.api import OpenMeteoClient
from weather_analytics.api.constants import (
    DEFAULT_FORECAST_DAYS,
    MAX_ECMWF_FORECAST_DAYS,
)
from weather_analytics.models.weather import Location

logger = logging.getLogger(__name__)


class WeatherExtractor:
    """Получает погодные данные для последующей обработки в ETL."""

    def __init__(self, client: OpenMeteoClient) -> None:
        """Принимает общий клиент Open-Meteo.

        Args:
            client: Настроенный API-клиент для получения погодных данных.
        """
        self.client = client

    def extract_historical(
        self,
        location: Location,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Получает суточные и почасовые исторические данные.

        Args:
            location: Географическая локация.
            start_date: Начало исторического периода.
            end_date: Конец исторического периода.

        Returns:
            Словарь с локацией, суточными и почасовыми данными.

        Raises:
            ValueError: При некорректных датах или ответе API.
            httpx.HTTPError: При сетевой ошибке или ошибочном HTTP-статусе.
        """
        if start_date > end_date:
            raise ValueError(
                'Начальная дата не может быть позже конечной'
            )

        logger.info(
            'Загрузка истории: %s (%s — %s)',
            location.name,
            start_date,
            end_date,
        )

        # Суточные и почасовые показатели запрашиваются отдельно,
        # поскольку API-клиент предоставляет специализированные методы.
        daily = self.client.get_historical_daily(
            location,
            start_date,
            end_date,
        )

        hourly = self.client.get_historical_hourly(
            location,
            start_date,
            end_date,
        )

        return {
            'location': location,
            'daily': daily['daily'],
            'hourly': hourly['hourly'],
        }

    def extract_forecast(
        self,
        location: Location,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
    ) -> dict[str, Any]:
        """Получает суточный, почасовой и ECMWF-прогнозы.

        Args:
            location: Географическая локация.
            forecast_days: Количество дней прогнозирования.

        Returns:
            Словарь с локацией и тремя наборами прогнозных данных.

        Raises:
            ValueError: При недопустимом количестве дней или ответе API.
            httpx.HTTPError: При сетевой ошибке или ошибочном HTTP-статусе.
        """
        # Все три набора загружаются вместе, поэтому используем
        # максимальный период специализированного прогноза ECMWF.
        if not 1 <= forecast_days <= MAX_ECMWF_FORECAST_DAYS:
            raise ValueError(
                f'Количество дней прогноза должно быть от 1 '
                f'до {MAX_ECMWF_FORECAST_DAYS}'
            )

        logger.info(
            'Загрузка прогноза: %s (%s дней)',
            location.name,
            forecast_days,
        )

        # Основной прогноз предоставляет суточные и почасовые
        # показатели, которые обрабатываются независимо.
        daily = self.client.get_forecast_daily(
            location,
            forecast_days,
        )

        hourly = self.client.get_forecast_hourly(
            location,
            forecast_days,
        )

        # ECMWF запрашиваем отдельно: эти показатели
        # сохраняются в собственной таблице PostgreSQL.
        ecmwf = self.client.get_ecmwf_hourly(
            location,
            forecast_days,
        )

        return {
            'location': location,
            'daily': daily['daily'],
            'hourly': hourly['hourly'],
            'ecmwf_hourly': ecmwf['hourly'],
        }

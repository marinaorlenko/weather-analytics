"""Локализация интерфейса Weather Analytics."""

import json
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRANSLATIONS_DIR = PROJECT_ROOT / 'data' / 'translations'


TEXTS = {
    'ru': {
        'subtitle': 'Аналитика исторической погоды и прогнозов',
        'settings': 'Параметры анализа',
        'city': 'Город',
        'history_tab': '📊 История',
        'forecast_tab': '🌤️ Прогноз на 7 дней',
        'compare_tab': '🏙️ Сравнение городов',
        'history': 'Историческая погода',
        'forecast': 'Прогноз на 7 дней',
        'period': 'Период анализа',
        'all': 'Весь доступный период',
        'last_7': 'Последние 7 дней',
        'last_30': 'Последние 30 дней',
        'last_365': 'Последние 365 дней',
        'custom': 'Произвольный диапазон',
        'date_range': 'Диапазон дат',
        'select_dates': 'Выберите начальную и конечную даты.',
        'no_data': 'За выбранный период данных нет.',
        'no_history': 'Исторические данные пока не загружены.',
        'no_forecast': 'Прогноз пока не загружен.',
        'no_hourly': 'Почасовые данные отсутствуют.',
        'days': 'Дней с наблюдениями',
        'average_temp': 'Средняя температура',
        'precip_total': 'Суммарные осадки',
        'forecast_precip': 'Ожидаемые осадки',
        'max_wind': 'Максимальная скорость ветра',
        'temperature': 'Динамика температуры',
        'min': 'Минимум',
        'max': 'Максимум',
        'precip_wind': 'Осадки и ветер',
        'precip': 'Ежедневные осадки',
        'wind': 'Максимальная скорость ветра',
        'hourly': 'Почасовая аналитика',
        'hourly_forecast': 'Почасовой прогноз',
        'hourly_temp': 'Температура по часам',
        'hourly_humidity': 'Относительная влажность по часам',
        'date': 'Дата',
        'datetime': 'Дата и время',
        'value': 'Значение',
        'indicator': 'Показатель',
        'temp_axis': 'Температура, °C',
        'precip_axis': 'Осадки, мм',
        'wind_axis': 'Скорость ветра, км/ч',
        'humidity_axis': 'Влажность, %',
        'no_precip': 'Осадки не зафиксированы (0 мм).',
        'no_precip_forecast': 'Осадки не ожидаются (0 мм).',
        'hour_count': 'Почасовых наблюдений',
        'timezone': 'Часовой пояс',
        'updated': 'Прогноз получен',
        'forecast_days': 'Дней в прогнозе',
        'source_data': 'Посмотреть исходные данные',
        'daily_data': 'Ежедневные наблюдения',
        'hourly_data': 'Почасовые наблюдения',
        'compare': 'Сравнение исторической погоды',
        'first_city': 'Первый город',
        'second_city': 'Второй город',
        'same_city': 'Выберите два разных города.',
        'need_cities': 'Для сравнения нужны минимум два города.',
        'need_history': 'Для одного из городов нет истории.',
        'no_common': 'У городов нет общих дат наблюдений.',
        'common_days': 'Общих дней наблюдений',
        'compare_temp': 'Оценка средней температуры, °C',
        'db_error': 'Ошибка загрузки данных',
        'extra_daily': 'Дополнительные ежедневные показатели',
        'extra_hourly': 'Дополнительные почасовые показатели',
        'ecmwf': 'Дополнительный прогноз ECMWF',
        'apparent_temperature_mean': 'Ощущаемая температура',
        'rain_sum': 'Дождь',
        'snowfall_sum': 'Снег',
        'sunshine_duration': 'Продолжительность солнечного сияния',
        'daylight_duration': 'Продолжительность светового дня',
        'shortwave_radiation_sum': 'Суммарная солнечная радиация',
        'precipitation_probability_max': 'Максимальная вероятность осадков',
        'uv_index_max': 'Максимальный УФ-индекс',
        'wind_gusts_max': 'Максимальные порывы ветра',
        'dew_point': 'Точка росы',
        'pressure_msl': 'Атмосферное давление',
        'cloud_cover': 'Облачность',
        'wind_gusts': 'Порывы ветра',
        'precipitation_probability': 'Вероятность осадков',
        'visibility': 'Видимость',
        'wind_speed': 'Скорость ветра',
        'cape': 'Конвективная энергия (CAPE)',
        'precipitation_type': 'Код типа осадков',
        'snowfall_water_equivalent': 'Водный эквивалент снега',
        'wet_bulb_temperature': 'Температура влажного термометра',
        'no_extra': 'Дополнительные показатели недоступны.',
    },
    'en': {
        'subtitle': 'Historical weather and forecast analytics',
        'settings': 'Analysis settings',
        'city': 'City',
        'history_tab': '📊 History',
        'forecast_tab': '🌤️ 7-day forecast',
        'compare_tab': '🏙️ Compare cities',
        'history': 'Historical weather',
        'forecast': '7-day forecast',
        'period': 'Analysis period',
        'all': 'All available data',
        'last_7': 'Last 7 days',
        'last_30': 'Last 30 days',
        'last_365': 'Last 365 days',
        'custom': 'Custom date range',
        'date_range': 'Date range',
        'select_dates': 'Select both start and end dates.',
        'no_data': 'No data for the selected period.',
        'no_history': 'Historical data is not available yet.',
        'no_forecast': 'Forecast data is not available yet.',
        'no_hourly': 'Hourly data is not available yet.',
        'days': 'Days with observations',
        'average_temp': 'Average temperature',
        'precip_total': 'Total precipitation',
        'forecast_precip': 'Expected precipitation',
        'max_wind': 'Maximum wind speed',
        'temperature': 'Temperature trends',
        'min': 'Minimum',
        'max': 'Maximum',
        'precip_wind': 'Precipitation and wind',
        'precip': 'Daily precipitation',
        'wind': 'Maximum wind speed',
        'hourly': 'Hourly analytics',
        'hourly_forecast': 'Hourly forecast',
        'hourly_temp': 'Hourly temperature',
        'hourly_humidity': 'Hourly relative humidity',
        'date': 'Date',
        'datetime': 'Date and time',
        'value': 'Value',
        'indicator': 'Metric',
        'temp_axis': 'Temperature, °C',
        'precip_axis': 'Precipitation, mm',
        'wind_axis': 'Wind speed, km/h',
        'humidity_axis': 'Humidity, %',
        'no_precip': 'No precipitation recorded (0 mm).',
        'no_precip_forecast': 'No precipitation expected (0 mm).',
        'hour_count': 'Hourly observations',
        'timezone': 'Time zone',
        'updated': 'Forecast retrieved',
        'forecast_days': 'Days in forecast',
        'source_data': 'View source data',
        'daily_data': 'Daily observations',
        'hourly_data': 'Hourly observations',
        'compare': 'Historical weather comparison',
        'first_city': 'First city',
        'second_city': 'Second city',
        'same_city': 'Select two different cities.',
        'need_cities': 'At least two cities are needed.',
        'need_history': 'Historical data is missing for one city.',
        'no_common': 'The cities have no common observation dates.',
        'common_days': 'Common observation days',
        'compare_temp': 'Estimated average temperature, °C',
        'db_error': 'Data loading error',
        'extra_daily': 'Additional daily metrics',
        'extra_hourly': 'Additional hourly metrics',
        'ecmwf': 'Additional ECMWF forecast',
        'apparent_temperature_mean': 'Feels-like temperature',
        'rain_sum': 'Rain',
        'snowfall_sum': 'Snowfall',
        'sunshine_duration': 'Sunshine duration',
        'daylight_duration': 'Daylight duration',
        'shortwave_radiation_sum': 'Total solar radiation',
        'precipitation_probability_max': 'Maximum precipitation probability',
        'uv_index_max': 'Maximum UV index',
        'wind_gusts_max': 'Maximum wind gusts',
        'dew_point': 'Dew point',
        'pressure_msl': 'Sea-level pressure',
        'cloud_cover': 'Cloud cover',
        'wind_gusts': 'Wind gusts',
        'precipitation_probability': 'Precipitation probability',
        'visibility': 'Visibility',
        'wind_speed': 'Wind speed',
        'cape': 'Convective available potential energy (CAPE)',
        'precipitation_type': 'Precipitation type code',
        'snowfall_water_equivalent': 'Snowfall water equivalent',
        'wet_bulb_temperature': 'Wet-bulb temperature',
        'no_extra': 'Additional metrics are unavailable.',
    },
}


@lru_cache(maxsize=2)
def load_names(filename: str) -> dict[str, str]:
    """Читает JSON-словарь географических названий."""
    path = TRANSLATIONS_DIR / filename

    with path.open(encoding='utf-8') as file:
        return json.load(file)


def translate(key: str, language: str = 'ru') -> str:
    """Возвращает перевод элемента интерфейса."""
    return TEXTS[language][key]


def city_name(name: str, country: str, language: str = 'ru') -> str:
    """Формирует отображаемое название города и страны."""
    if language == 'en':
        return f'{name}, {country}'

    cities = load_names('cities.json')
    countries = load_names('countries.json')

    city_ru = cities.get(name, name)
    country_ru = countries.get(country, country)

    return f'{city_ru}, {country_ru}'


def city_search_name(name: str, country: str, language: str = 'ru') -> str:
    """Формирует подпись с названиями на двух языках для поиска."""
    original = f'{name}, {country}'
    translated = city_name(name, country, 'ru')

    if translated == original:
        return original

    if language == 'ru':
        return f'{translated} ({original})'

    return f'{original} ({translated})'

"""Константы погодных параметров для запросов к Open-Meteo.

Модуль содержит наборы полей для исторических данных, прогнозов,
специализированных моделей ECMWF и Telegram-бота Stormy.

Названия параметров соответствуют спецификации Open-Meteo.
Все наборы представлены неизменяемыми кортежами.
"""

# ============================================================
# ИСТОРИЧЕСКИЕ ДАННЫЕ
# ============================================================

# Почасовые исторические показатели для аналитического ETL.
HISTORICAL_HOURLY = (
    'temperature_2m',
    'relative_humidity_2m',
    'dew_point_2m',
    'apparent_temperature',
    'precipitation',
    'rain',
    'snowfall',
    'snow_depth',
    'weather_code',
    'pressure_msl',
    'surface_pressure',
    'cloud_cover',
    'cloud_cover_low',
    'cloud_cover_mid',
    'cloud_cover_high',
    'wind_speed_10m',
    'wind_direction_10m',
    'wind_gusts_10m',
    'shortwave_radiation',
    'direct_radiation',
    'diffuse_radiation',
    'sunshine_duration',
    'et0_fao_evapotranspiration',
    'vapour_pressure_deficit',
    'wet_bulb_temperature_2m',
    'is_day',
)

# Суточные исторические показатели для аналитического ETL.
HISTORICAL_DAILY = (
    'weather_code',
    'temperature_2m_mean',
    'temperature_2m_min',
    'temperature_2m_max',
    'apparent_temperature_mean',
    'apparent_temperature_min',
    'apparent_temperature_max',
    'sunrise',
    'sunset',
    'daylight_duration',
    'sunshine_duration',
    'precipitation_sum',
    'rain_sum',
    'snowfall_sum',
    'precipitation_hours',
    'wind_speed_10m_max',
    'wind_gusts_10m_max',
    'wind_direction_10m_dominant',
    'shortwave_radiation_sum',
    'et0_fao_evapotranspiration',
)


# ============================================================
# ПРОГНОЗНЫЕ ДАННЫЕ
# ============================================================

# Расширенные почасовые прогнозы для аналитического ETL.
# Включают вероятность осадков, облачность, видимость,
# УФ-индекс и показатели атмосферной нестабильности.
FORECAST_HOURLY = (
    'temperature_2m',
    'relative_humidity_2m',
    'dew_point_2m',
    'apparent_temperature',
    'precipitation_probability',
    'precipitation',
    'rain',
    'showers',
    'snowfall',
    'snow_depth',
    'weather_code',
    'pressure_msl',
    'surface_pressure',
    'cloud_cover',
    'cloud_cover_low',
    'cloud_cover_mid',
    'cloud_cover_high',
    'visibility',
    'evapotranspiration',
    'et0_fao_evapotranspiration',
    'vapour_pressure_deficit',
    'wind_speed_10m',
    'wind_direction_10m',
    'wind_gusts_10m',
    'shortwave_radiation',
    'direct_radiation',
    'diffuse_radiation',
    'uv_index',
    'uv_index_clear_sky',
    'sunshine_duration',
    'wet_bulb_temperature_2m',
    'cape',
    'lifted_index',
    'convective_inhibition',
    'freezing_level_height',
    'is_day',
)

# Расширенные суточные прогнозы для аналитического ETL.
FORECAST_DAILY = (
    'weather_code',
    'temperature_2m_mean',
    'temperature_2m_min',
    'temperature_2m_max',
    'apparent_temperature_mean',
    'apparent_temperature_min',
    'apparent_temperature_max',
    'sunrise',
    'sunset',
    'daylight_duration',
    'sunshine_duration',
    'precipitation_sum',
    'rain_sum',
    'showers_sum',
    'snowfall_sum',
    'precipitation_hours',
    'precipitation_probability_max',
    'precipitation_probability_mean',
    'wind_speed_10m_max',
    'wind_gusts_10m_max',
    'wind_direction_10m_dominant',
    'shortwave_radiation_sum',
    'uv_index_max',
    'uv_index_clear_sky_max',
    'et0_fao_evapotranspiration',
)


# ============================================================
# СПЕЦИАЛИЗИРОВАННЫЕ ДАННЫЕ ECMWF
# ============================================================

# Дополнительные параметры модели ECMWF, используемые
# для анализа осадков, снежного покрова и грозовых условий.
ECMWF_HOURLY = (
    'precipitation_type',
    'lightning_density',
    'snowfall_water_equivalent',
    'snow_depth_water_equivalent',
    'cape',
    'convective_inhibition',
    'wet_bulb_temperature_2m',
)


# ============================================================
# TELEGRAM-БОТ STORMY
# ============================================================

# Текущая погода: основные показатели для ответа пользователю.
# Отдельный набор позволяет не загружать расширенные поля ETL.
BOT_CURRENT = (
    'temperature_2m',
    'apparent_temperature',
    'relative_humidity_2m',
    'wind_speed_10m',
    'wind_gusts_10m',
    'wind_direction_10m',
    'precipitation',
    'rain',
    'snowfall',
    'weather_code',
    'cloud_cover',
    'pressure_msl',
)

# Суточные показатели для исторических и прогнозных запросов.
BOT_DAILY = (
    'temperature_2m_min',
    'temperature_2m_max',
    'temperature_2m_mean',
    'apparent_temperature_mean',
    'precipitation_sum',
    'rain_sum',
    'snowfall_sum',
    'precipitation_hours',
    'wind_speed_10m_max',
    'wind_gusts_10m_max',
    'wind_direction_10m_dominant',
    'weather_code',
)

# Почасовые показатели для исторических и прогнозных запросов.
BOT_HOURLY = (
    'relative_humidity_2m',
    'cloud_cover',
    'pressure_msl',
    'precipitation',
    'rain',
    'snowfall',
    'weather_code',
    'wind_speed_10m',
    'temperature_2m',
    'apparent_temperature',
)

# Дополнительные суточные показатели, доступные в прогнозе.
BOT_FORECAST_DAILY_EXTRA = (
    'precipitation_probability_max',
    'uv_index_max',
)

# Дополнительные почасовые показатели прогнозного API.
BOT_FORECAST_HOURLY_EXTRA = (
    'showers',
    'precipitation_probability',
)


# ============================================================
# ГЕОКОДИРОВАНИЕ
# ============================================================

# Значения по умолчанию и ограничения поиска населённых пунктов.
DEFAULT_LANGUAGE = 'en'
DEFAULT_RESULT_COUNT = 10
MAX_RESULT_COUNT = 100
MIN_CITY_LENGTH = 2


# ============================================================
# ОГРАНИЧЕНИЯ ПРОГНОЗНЫХ ЗАПРОСОВ
# ============================================================

# Продолжительность прогноза по умолчанию и максимальные
# значения для стандартного API и специализированного ECMWF.
DEFAULT_FORECAST_DAYS = 7
MAX_FORECAST_DAYS = 16
MAX_ECMWF_FORECAST_DAYS = 15


# ============================================================
# БАЗОВЫЕ ПОКАЗАТЕЛИ ТЕКУЩЕЙ ПОГОДЫ
# ============================================================

# Минимальный набор для модели CurrentWeather.
CURRENT_WEATHER_FIELDS = (
    'temperature_2m',
    'relative_humidity_2m',
    'wind_speed_10m',
)

# ============================================================
# HTTP-ЗАПРОСЫ И ПОВТОРНЫЕ ПОПЫТКИ
# ============================================================

# Временные HTTP-ошибки, при которых разрешён повтор запроса.
RETRYABLE_HTTP_STATUSES = frozenset(
    {
        429,
        500,
        502,
        503,
        504,
    }
)

# Максимальное количество повторов после первой попытки.
HTTP_MAX_RETRIES = 3

# Экспоненциальное увеличение паузы между повторами.
HTTP_RETRY_BASE_DELAY = 2.0
HTTP_RETRY_BACKOFF_FACTOR = 2.0
HTTP_RETRY_MAX_DELAY = 60.0

# Количество первоначальных попыток до повторов.
HTTP_INITIAL_ATTEMPTS = 1

# Начальное значение таймера ограничителя запросов.
HTTP_RATE_LIMIT_INITIAL_TIME = 0.0

"""Цветовая палитра и единицы измерения погодного дашборда."""

STEEL_BLUE = '#4682B4'
SAGE_GREEN = '#79B59B'
DEEP_BLUE = '#354E68'

EXTRA_COLORS = (STEEL_BLUE, SAGE_GREEN, DEEP_BLUE)

EXTRA_UNITS = {
    'apparent_temperature_mean': '°C',
    'rain_sum': 'мм',
    'snowfall_sum': 'см',
    'sunshine_duration': 'ч',
    'daylight_duration': 'ч',
    'shortwave_radiation_sum': 'МДж/м²',
    'precipitation_probability_max': '%',
    'uv_index_max': '',
    'wind_gusts_max': 'км/ч',
    'dew_point': '°C',
    'pressure_msl': 'мм рт. ст.',
    'cloud_cover': '%',
    'wind_gusts': 'км/ч',
    'precipitation_probability': '%',
    'visibility': 'м',
    'wind_speed': 'км/ч',
    'cape': 'Дж/кг',
    'precipitation_type': '',
    'snowfall_water_equivalent': 'мм',
    'wet_bulb_temperature': '°C',
}

# Белый список столбцов PostgreSQL для дополнительных показателей.
# Используется для проверки динамически формируемых SQL-запросов.
# Хранится отдельно от EXTRA_UNITS, поскольку не каждый показатель
# интерфейса обязательно соответствует физическому столбцу БД.
EXTRA_METRIC_COLUMNS = frozenset(
    {
        'apparent_temperature_mean',
        'rain_sum',
        'snowfall_sum',
        'sunshine_duration',
        'daylight_duration',
        'shortwave_radiation_sum',
        'precipitation_probability_max',
        'uv_index_max',
        'wind_gusts_max',
        'dew_point',
        'pressure_msl',
        'cloud_cover',
        'wind_gusts',
        'precipitation_probability',
        'visibility',
        'wind_speed',
        'cape',
        'precipitation_type',
        'snowfall_water_equivalent',
        'wet_bulb_temperature',
    }
)

# Дополнительные цвета для категорий тепловой нагрузки.
HEAT_HIGH_COLOR = '#9367A8'
HEAT_VERY_HIGH_COLOR = '#B34D69'

# Границы категорий тепловой нагрузки по ощущаемой температуре, °C.
HEAT_ELEVATED_THRESHOLD = 32
HEAT_HIGH_THRESHOLD = 40
HEAT_VERY_HIGH_THRESHOLD = 50

# Параметры приблизительного расчёта лунного цикла.
SYNODIC_MONTH_DAYS = 29.530588853

# Коэффициент перевода атмосферного давления из гПа в мм рт. ст.
HPA_TO_MMHG = 0.750061683

# Дополнительные показатели исторической погоды для графиков.
HISTORY_DAILY_EXTRA = (
    'apparent_temperature_mean',
    'rain_sum',
    'snowfall_sum',
    'wind_gusts_max',
)

HISTORY_HOURLY_EXTRA = (
    'dew_point',
    'pressure_msl',
    'cloud_cover',
    'wind_gusts',
)

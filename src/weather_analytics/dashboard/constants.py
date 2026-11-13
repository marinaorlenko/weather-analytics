"""Цветовая палитра и единицы измерения погодного дашборда."""

# Основная палитра.
STEEL_BLUE = '#4682B4'
SAGE_GREEN = '#79B59B'
DEEP_BLUE = '#354E68'

# Дополнительные приглушённые оттенки.
LIGHT_CORAL = '#F08080'
MUTED_BLUE = '#58799A'
TURQUOISE_GREEN = '#5B9E91'
CLOUD_BLUE = '#8998A5'
MUTED_PURPLE = '#8D83B5'

# Палитра дополнительных графиков.
# Сохраняется для совместимости с существующими модулями.
EXTRA_COLORS = (STEEL_BLUE, SAGE_GREEN, DEEP_BLUE)

# Постоянные цвета погодных показателей.
# Не зависят от порядка отображения графиков.
METRIC_COLORS = {
    'temperature_min': LIGHT_CORAL,
    'average_temperature': STEEL_BLUE,
    'temperature_max': SAGE_GREEN,
    'temperature': STEEL_BLUE,
    'apparent_temperature_mean': STEEL_BLUE,
    'humidity': TURQUOISE_GREEN,
    'dew_point': TURQUOISE_GREEN,
    'wind_speed': MUTED_BLUE,
    'wind_speed_max': MUTED_BLUE,
    'wind_gusts': MUTED_BLUE,
    'wind_gusts_max': MUTED_BLUE,
    'wind_direction_dominant': MUTED_BLUE,
    'cloud_cover': CLOUD_BLUE,
    'pressure_msl': MUTED_PURPLE,
    'precipitation': STEEL_BLUE,
    'rain_sum': STEEL_BLUE,
    'snowfall_sum': SAGE_GREEN,
    'precipitation_probability': STEEL_BLUE,
    'precipitation_probability_max': STEEL_BLUE,
    'precipitation_type': STEEL_BLUE,
    'snowfall_water_equivalent': SAGE_GREEN,
    'sunshine_duration': SAGE_GREEN,
    'daylight_duration': SAGE_GREEN,
    'shortwave_radiation_sum': STEEL_BLUE,
    'uv_index_max': MUTED_PURPLE,
    'visibility': CLOUD_BLUE,
    'cape': MUTED_PURPLE,
    'wet_bulb_temperature': TURQUOISE_GREEN,
}

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

"""Соответствие полей Open-Meteo столбцам PostgreSQL.

Словари используются WeatherTransformer для преобразования
ответов API в записи погодных таблиц.
"""

# Суточные исторические показатели.
HISTORICAL_DAILY_FIELDS = {
    'weather_code': 'weather_code',
    'temperature_2m_mean': 'temperature_mean',
    'temperature_2m_min': 'temperature_min',
    'temperature_2m_max': 'temperature_max',
    'apparent_temperature_mean': 'apparent_temperature_mean',
    'apparent_temperature_min': 'apparent_temperature_min',
    'apparent_temperature_max': 'apparent_temperature_max',
    'daylight_duration': 'daylight_duration',
    'sunshine_duration': 'sunshine_duration',
    'precipitation_sum': 'precipitation',
    'rain_sum': 'rain_sum',
    'snowfall_sum': 'snowfall_sum',
    'precipitation_hours': 'precipitation_hours',
    'wind_speed_10m_max': 'wind_speed_max',
    'wind_gusts_10m_max': 'wind_gusts_max',
    'wind_direction_10m_dominant': 'wind_direction_dominant',
    'shortwave_radiation_sum': 'shortwave_radiation_sum',
    'et0_fao_evapotranspiration': 'et0_fao_evapotranspiration',
}

# Почасовые исторические показатели.
HISTORICAL_HOURLY_FIELDS = {
    'temperature_2m': 'temperature',
    'relative_humidity_2m': 'humidity',
    'dew_point_2m': 'dew_point',
    'apparent_temperature': 'apparent_temperature',
    'precipitation': 'precipitation',
    'rain': 'rain',
    'snowfall': 'snowfall',
    'snow_depth': 'snow_depth',
    'weather_code': 'weather_code',
    'pressure_msl': 'pressure_msl',
    'surface_pressure': 'surface_pressure',
    'cloud_cover': 'cloud_cover',
    'cloud_cover_low': 'cloud_cover_low',
    'cloud_cover_mid': 'cloud_cover_mid',
    'cloud_cover_high': 'cloud_cover_high',
    'wind_speed_10m': 'wind_speed',
    'wind_direction_10m': 'wind_direction',
    'wind_gusts_10m': 'wind_gusts',
    'shortwave_radiation': 'shortwave_radiation',
    'direct_radiation': 'direct_radiation',
    'diffuse_radiation': 'diffuse_radiation',
    'sunshine_duration': 'sunshine_duration',
    'et0_fao_evapotranspiration': 'et0_fao_evapotranspiration',
    'vapour_pressure_deficit': 'vapour_pressure_deficit',
    'wet_bulb_temperature_2m': 'wet_bulb_temperature',
}

# Суточные прогнозные показатели.
FORECAST_DAILY_FIELDS = {
    **HISTORICAL_DAILY_FIELDS,
    'showers_sum': 'showers_sum',
    'precipitation_probability_max': 'precipitation_probability_max',
    'precipitation_probability_mean': 'precipitation_probability_mean',
    'uv_index_max': 'uv_index_max',
    'uv_index_clear_sky_max': 'uv_index_clear_sky_max',
}

# Почасовые прогнозные показатели.
FORECAST_HOURLY_FIELDS = {
    **HISTORICAL_HOURLY_FIELDS,
    'precipitation_probability': 'precipitation_probability',
    'showers': 'showers',
    'visibility': 'visibility',
    'evapotranspiration': 'evapotranspiration',
    'uv_index': 'uv_index',
    'uv_index_clear_sky': 'uv_index_clear_sky',
    'cape': 'cape',
    'lifted_index': 'lifted_index',
    'convective_inhibition': 'convective_inhibition',
    'freezing_level_height': 'freezing_level_height',
}

# Специализированные почасовые показатели ECMWF.
ECMWF_HOURLY_FIELDS = {
    'precipitation_type': 'precipitation_type',
    'snowfall_water_equivalent': 'snowfall_water_equivalent',
    'snow_depth_water_equivalent': 'snow_depth_water_equivalent',
    'cape': 'cape',
    'wet_bulb_temperature_2m': 'wet_bulb_temperature',
    'lightning_density': 'lightning_density',
    'convective_inhibition': 'convective_inhibition',
}

"""Загрузка расширенного дневного прогноза для интерфейса."""

import pandas as pd
import streamlit as st

from weather_analytics.dashboard.data import get_connection


@st.cache_data(ttl=300)
def load_forecast_overview(city_id: int) -> pd.DataFrame:
    """Загружает последнюю версию дневного прогноза со всеми основными метриками."""
    query = """
        SELECT
            forecast_date,
            fetched_at,
            temperature_min,
            temperature_mean,
            temperature_max,
            apparent_temperature_mean,
            precipitation,
            precipitation_probability_max,
            wind_speed_max,
            wind_gusts_max,
            wind_direction_dominant,
            uv_index_max,
            sunrise,
            sunset,
            daylight_duration
        FROM forecast_daily
        WHERE city_id = %s
          AND fetched_at = (
              SELECT MAX(fetched_at)
              FROM forecast_daily
              WHERE city_id = %s
          )
        ORDER BY forecast_date
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (city_id, city_id))
            records = cursor.fetchall()
            columns = [column.name for column in cursor.description]

    dataframe = pd.DataFrame(records, columns=columns)

    if not dataframe.empty:
        dataframe['forecast_date'] = pd.to_datetime(
            dataframe['forecast_date'],
        )
        dataframe['fetched_at'] = pd.to_datetime(
            dataframe['fetched_at'],
            utc=True,
        )

    return dataframe

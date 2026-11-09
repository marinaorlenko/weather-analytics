"""Загрузка погодных данных из PostgreSQL для Streamlit-дашборда."""

import pandas as pd
import psycopg
import streamlit as st

from weather_analytics.config import get_settings
from weather_analytics.dashboard.constants import EXTRA_METRIC_COLUMNS


def get_connection() -> psycopg.Connection:
    """Создаёт подключение к базе данных PostgreSQL."""
    settings = get_settings()

    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        dbname=settings.db_name,
    )


def get_utc_date_bounds(
    start_date: str,
    end_date: str,
    timezone: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Возвращает UTC-границы диапазона местных календарных дат."""
    if pd.Timestamp(start_date) > pd.Timestamp(end_date):
        raise ValueError('Начальная дата не может быть позже конечной')

    # Сначала определяем границы местных календарных суток.
    # Прибавляем календарный день до локализации, чтобы корректно
    # учитывать переходы на летнее и зимнее время.
    start_local = pd.Timestamp(start_date).tz_localize(timezone)
    end_local = (
        pd.Timestamp(end_date) + pd.Timedelta(days=1)
    ).tz_localize(timezone)

    return start_local.tz_convert('UTC'), end_local.tz_convert('UTC')


@st.cache_data(ttl=300)
def load_cities() -> pd.DataFrame:
    """Загружает список городов и их часовых поясов."""
    query = """
        SELECT city_id, name, country, timezone
        FROM cities
        WHERE is_active = TRUE
        ORDER BY name, country
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            records = cursor.fetchall()

    return pd.DataFrame(
        records,
        columns=['city_id', 'name', 'country', 'timezone'],
    )


@st.cache_data(ttl=300)
def load_historical_daily(city_id: int) -> pd.DataFrame:
    """Загружает ежедневные исторические наблюдения."""
    query = """
        SELECT
            weather_date,
            temperature_min,
            temperature_max,
            precipitation,
            wind_speed_max,
            wind_direction_dominant,
            sunrise,
            sunset
        FROM historical_daily
        WHERE city_id = %s
        ORDER BY weather_date
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (city_id,))
            records = cursor.fetchall()

    dataframe = pd.DataFrame(
        records,
        columns=[
            'weather_date',
            'temperature_min',
            'temperature_max',
            'precipitation',
            'wind_speed_max',
            'wind_direction_dominant',
            'sunrise',
            'sunset',
        ],
    )

    if not dataframe.empty:
        dataframe['weather_date'] = pd.to_datetime(dataframe['weather_date'])

    return dataframe


@st.cache_data(ttl=300)
def load_historical_hourly(
    city_id: int,
    start_date: str,
    end_date: str,
    timezone: str,
) -> pd.DataFrame:
    """Загружает почасовую историю за диапазон местных дат города."""
    start_utc, end_utc = get_utc_date_bounds(
        start_date,
        end_date,
        timezone,
    )

    query = """
        SELECT
            weather_time,
            temperature,
            humidity
        FROM historical_hourly
        WHERE city_id = %s
          AND weather_time >= %s
          AND weather_time < %s
        ORDER BY weather_time
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (city_id, start_utc.to_pydatetime(), end_utc.to_pydatetime()),
            )
            records = cursor.fetchall()

    dataframe = pd.DataFrame(
        records,
        columns=['weather_time', 'temperature', 'humidity'],
    )

    if not dataframe.empty:
        dataframe['weather_time'] = pd.to_datetime(
            dataframe['weather_time'],
            utc=True,
        )

    return dataframe


@st.cache_data(ttl=300)
def load_forecast_daily(city_id: int) -> pd.DataFrame:
    """Загружает последнюю сохранённую версию прогноза по дням."""
    query = """
        SELECT
            forecast_date,
            temperature_min,
            temperature_max,
            precipitation,
            wind_speed_max,
            fetched_at
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

    dataframe = pd.DataFrame(
        records,
        columns=[
            'forecast_date',
            'temperature_min',
            'temperature_max',
            'precipitation',
            'wind_speed_max',
            'fetched_at',
        ],
    )

    if not dataframe.empty:
        dataframe['forecast_date'] = pd.to_datetime(dataframe['forecast_date'])
        dataframe['fetched_at'] = pd.to_datetime(
            dataframe['fetched_at'],
            utc=True,
        )

    return dataframe


@st.cache_data(ttl=300)
def load_forecast_hourly(
    city_id: int,
    fetched_at: pd.Timestamp,
) -> pd.DataFrame:
    """Загружает почасовой прогноз из той же версии, что и дневной."""
    query = """
        SELECT
            forecast_time,
            temperature,
            humidity
        FROM forecast_hourly
        WHERE city_id = %s
          AND fetched_at = %s
        ORDER BY forecast_time
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (city_id, fetched_at.to_pydatetime()),
            )
            records = cursor.fetchall()

    dataframe = pd.DataFrame(
        records,
        columns=['forecast_time', 'temperature', 'humidity'],
    )

    if not dataframe.empty:
        dataframe['forecast_time'] = pd.to_datetime(
            dataframe['forecast_time'],
            utc=True,
        )

    return dataframe


@st.cache_data(ttl=300)
def load_historical_daily_averages(
    city_id: int,
    timezone: str,
) -> pd.DataFrame:
    """Вычисляет среднюю температуру по часам за местные сутки города."""
    query = """
        SELECT
            (weather_time AT TIME ZONE %s)::date AS weather_date,
            AVG(temperature) AS average_temperature,
            COUNT(DISTINCT weather_time) AS hour_count,
            COUNT(temperature) AS temperature_count
        FROM historical_hourly
        WHERE city_id = %s
        GROUP BY 1
        ORDER BY 1
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (timezone, city_id))
            records = cursor.fetchall()

    return prepare_complete_daily_averages(
        records,
        'weather_date',
        timezone,
    )


@st.cache_data(ttl=300)
def load_forecast_daily_averages(
    city_id: int,
    timezone: str,
    fetched_at: pd.Timestamp,
) -> pd.DataFrame:
    """Вычисляет суточные средние по последней версии почасового прогноза."""
    query = """
        SELECT
            (forecast_time AT TIME ZONE %s)::date AS forecast_date,
            AVG(temperature) AS average_temperature,
            COUNT(DISTINCT forecast_time) AS hour_count,
            COUNT(temperature) AS temperature_count
        FROM forecast_hourly
        WHERE city_id = %s AND fetched_at = %s
        GROUP BY 1
        ORDER BY 1
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (timezone, city_id, fetched_at.to_pydatetime()),
            )
            records = cursor.fetchall()

    return prepare_complete_daily_averages(
        records,
        'forecast_date',
        timezone,
    )


def prepare_complete_daily_averages(
    records: list,
    date_column: str,
    timezone: str,
) -> pd.DataFrame:
    """Оставляет только сутки с полным набором температурных наблюдений."""
    dataframe = pd.DataFrame(
        records,
        columns=[
            date_column,
            'average_temperature',
            'hour_count',
            'temperature_count',
        ],
    )

    if dataframe.empty:
        return pd.DataFrame(
            columns=[date_column, 'average_temperature'],
        )

    dataframe[date_column] = pd.to_datetime(dataframe[date_column])
    dataframe['average_temperature'] = pd.to_numeric(
        dataframe['average_temperature'],
        errors='coerce',
    )

    # Учитываем сутки продолжительностью 23 или 25 часов
    # при переходе на летнее или зимнее время.
    local_midnight = dataframe[date_column].dt.tz_localize(
        timezone,
        ambiguous='NaT',
        nonexistent='shift_forward',
    )
    next_midnight = (dataframe[date_column] + pd.Timedelta(days=1)).dt.tz_localize(
        timezone,
        ambiguous='NaT',
        nonexistent='shift_forward',
    )

    expected_hours = (next_midnight - local_midnight).dt.total_seconds() / 3600

    # Среднее рассчитываем только для суток, где присутствуют
    # все ожидаемые почасовые значения температуры.
    complete = dataframe['hour_count'].eq(expected_hours) & dataframe[
        'temperature_count'
    ].eq(expected_hours)

    return dataframe.loc[
        complete,
        [date_column, 'average_temperature'],
    ].copy()


@st.cache_data(ttl=300)
def load_extra_metrics(
    table_name: str,
    city_id: int,
    columns: tuple[str, ...],
    fetched_at: pd.Timestamp | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    timezone: str | None = None,
) -> pd.DataFrame:
    """Загружает дополнительные показатели из разрешённых погодных таблиц."""
    allowed = {
        'historical_daily': 'weather_date',
        'historical_hourly': 'weather_time',
        'forecast_daily': 'forecast_date',
        'forecast_hourly': 'forecast_time',
        'forecast_ecmwf_hourly': 'forecast_time',
    }

    if table_name not in allowed:
        raise ValueError(f'Недопустимая таблица: {table_name}')

    # Проверяем названия столбцов перед формированием SQL-запроса.
    time_column = allowed[table_name]

    if not columns:
        raise ValueError('Не выбраны погодные показатели')

    if not set(columns).issubset(EXTRA_METRIC_COLUMNS):
        raise ValueError('Недопустимые названия погодных показателей')

    query = (
        f'SELECT {time_column}, {", ".join(columns)} '
        f'FROM {table_name} WHERE city_id = %s'
    )

    params = [city_id]

    # Для прогноза используем конкретную сохранённую версию данных.
    if table_name.startswith('forecast_'):
        if fetched_at is None:
            raise ValueError('Для прогноза необходим fetched_at')

        query += ' AND fetched_at = %s'
        params.append(fetched_at.to_pydatetime())

    # Для исторических почасовых данных ограничиваем выборку
    # UTC-границами местных суток непосредственно в PostgreSQL.
    if table_name == 'historical_hourly':
        if any(value is not None for value in (start_date, end_date, timezone)):
            if not all(value is not None for value in (start_date, end_date, timezone)):
                raise ValueError(
                    'Для диапазона исторических часов необходимы '
                    'start_date, end_date и timezone'
                )

            start_utc, end_utc = get_utc_date_bounds(
                start_date,
                end_date,
                timezone,
            )

            query += f' AND {time_column} >= %s AND {time_column} < %s'
            params.extend(
                [start_utc.to_pydatetime(), end_utc.to_pydatetime()]
            )

    query += f' ORDER BY {time_column}'

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            records = cursor.fetchall()

    result = pd.DataFrame(
        records,
        columns=[time_column, *columns],
    )

    if not result.empty:
        result[time_column] = pd.to_datetime(
            result[time_column],
            utc=table_name.endswith('hourly'),
        )

        for column in columns:
            result[column] = pd.to_numeric(
                result[column],
                errors='coerce',
            )

    return result


@st.cache_data(ttl=300)
def load_forecast_hourly_details(
    city_id: int,
    fetched_at: pd.Timestamp,
) -> pd.DataFrame:
    """Загружает почасовые показатели без зависимости от необязательных полей."""
    fields = (
        'temperature',
        'apparent_temperature',
        'humidity',
        'precipitation_probability',
        'uv_index',
        'wind_speed',
        'wind_gusts',
        'dew_point',
        'cloud_cover',
        'pressure_msl',
        'visibility',
    )
    # Необязательные поля читаем из JSON-представления строки.
    expressions = ', '.join(
        f"(to_jsonb(t)->>'{field}')::double precision AS {field}" for field in fields
    )
    query = f"""
        SELECT t.forecast_time, {expressions}
        FROM forecast_hourly AS t
        WHERE t.city_id = %s AND t.fetched_at = %s
        ORDER BY t.forecast_time
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (city_id, fetched_at.to_pydatetime()))
            rows = cursor.fetchall()
    result = pd.DataFrame(rows, columns=['forecast_time', *fields])
    if not result.empty:
        result['forecast_time'] = pd.to_datetime(result['forecast_time'], utc=True)
        for field in fields:
            result[field] = pd.to_numeric(result[field], errors='coerce')
    return result


@st.cache_data(ttl=300)
def load_forecast_precipitation_events(
    city_id: int,
    fetched_at: pd.Timestamp,
) -> pd.DataFrame:
    """Возвращает только часы с ненулевыми осадками и сопутствующим кодом ECMWF."""
    query = """
        SELECT h.forecast_time, h.precipitation, h.rain, h.showers,
               h.snowfall, e.precipitation_type
        FROM forecast_hourly AS h
        LEFT JOIN forecast_ecmwf_hourly AS e
          ON e.city_id = h.city_id
         AND e.fetched_at = h.fetched_at
         AND e.forecast_time = h.forecast_time
        WHERE h.city_id = %s AND h.fetched_at = %s
          AND (COALESCE(h.precipitation, 0) > 0
            OR COALESCE(h.rain, 0) > 0
            OR COALESCE(h.showers, 0) > 0
            OR COALESCE(h.snowfall, 0) > 0)
        ORDER BY h.forecast_time
    """
    columns = (
        'forecast_time',
        'precipitation',
        'rain',
        'showers',
        'snowfall',
        'precipitation_type',
    )
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (city_id, fetched_at.to_pydatetime()))
            rows = cursor.fetchall()
    result = pd.DataFrame(rows, columns=columns)
    if not result.empty:
        result['forecast_time'] = pd.to_datetime(result['forecast_time'], utc=True)
    return result

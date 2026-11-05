"""Аналитический дашборд исторической погоды и прогнозов."""


import psycopg
import streamlit as st

from weather_analytics.dashboard.comparison import render_comparison_tab
from weather_analytics.dashboard.data import load_cities
from weather_analytics.dashboard.forecast import render_forecast_tab
from weather_analytics.dashboard.history import render_history_tab
from weather_analytics.localization import city_name, translate

# ---------------------------------------------------------
# Настройки страницы и палитра
# ---------------------------------------------------------

st.set_page_config(
    page_title='Weather Analytics',
    page_icon='🌍',
    layout='wide',
)


# ---------------------------------------------------------
# Подготовка данных для графиков
# ---------------------------------------------------------

# HISTORY_DAILY_EXTRA = (
#     'apparent_temperature_mean', 'rain_sum', 'snowfall_sum',
#     'sunshine_duration', 'shortwave_radiation_sum',
# )
# HISTORY_HOURLY_EXTRA = (
#     'dew_point', 'pressure_msl', 'cloud_cover', 'wind_gusts',
# )
# FORECAST_DAILY_EXTRA = (
#     'apparent_temperature_mean', 'precipitation_probability_max',
#     'uv_index_max', 'wind_gusts_max', 'daylight_duration',
# )
# FORECAST_HOURLY_EXTRA = (
#     'precipitation_probability', 'pressure_msl', 'cloud_cover',
#     'visibility', 'wind_speed', 'wind_gusts',
# )
# ECMWF_EXTRA = (
#     'cape', 'precipitation_type', 'snowfall_water_equivalent',
#     'wet_bulb_temperature',
# )


# ---------------------------------------------------------
# Настройки интерфейса
# ---------------------------------------------------------

selected_language = st.sidebar.selectbox(
    'Language / Язык',
    options=['Русский', 'English'],
    key='dashboard_language',
)

language = (
    'ru'
    if selected_language == 'Русский'
    else 'en'
)

st.title('🌍 Weather Analytics')
st.caption(translate('subtitle', language))

try:
    cities = load_cities()
except psycopg.Error as error:
    st.error(
        f'{translate("db_error", language)}: {error}'
    )
    st.stop()

if cities.empty:
    st.info(translate('no_data', language))
    st.stop()


# Сопоставляем идентификаторы городов с отображаемыми названиями.
# Идентификатор не зависит от языка интерфейса.
city_records = {
    int(row.city_id): {
        'name': row.name,
        'country': row.country,
        'timezone': row.timezone,
    }
    for row in cities.itertuples(index=False)
}

city_ids = sorted(
    city_records,
    key=lambda city_id: city_name(
        city_records[city_id]['name'],
        city_records[city_id]['country'],
        language,
    ),
)

# При смене языка пересоздаём отображение списка городов.
# Выбранный city_id сохраняется независимо от языка.
if 'current_city_id' not in st.session_state:
    st.session_state.current_city_id = city_ids[0]

selected_city_id = st.sidebar.selectbox(
    translate('city', language),
    options=city_ids,
    index=(
        city_ids.index(st.session_state.current_city_id)
        if st.session_state.current_city_id in city_ids
        else 0
    ),
    format_func=lambda city_id: city_name(
        city_records[city_id]['name'],
        city_records[city_id]['country'],
        language,
    ),
    key=f'selected_city_{language}',
)

st.session_state.current_city_id = selected_city_id

selected_city = city_records[selected_city_id]
city_timezone = selected_city['timezone']

city_label = city_name(
    selected_city['name'],
    selected_city['country'],
    language,
)

st.subheader(city_label)
st.caption(
    f'{translate("timezone", language)}: {city_timezone}'
)


# ---------------------------------------------------------
# Вкладки дашборда
# ---------------------------------------------------------

history_tab, forecast_tab, comparison_tab = st.tabs([
    translate('history_tab', language),
    translate('forecast_tab', language),
    translate('compare_tab', language),
])

# =========================================================
# Вкладка 1. Историческая погода
# =========================================================

with history_tab:
    render_history_tab(
        selected_city_id=selected_city_id,
        city_timezone=city_timezone,
        language=language,
    )

# =========================================================
# Вкладка 2. Прогноз на 7 дней
# =========================================================

with forecast_tab:
    render_forecast_tab(
        selected_city_id=selected_city_id,
        city_timezone=city_timezone,
        language=language,
    )


# =========================================================
# Вкладка 3. Сравнение городов
# =========================================================

render_comparison_tab(
    comparison_tab=comparison_tab,
    city_ids=city_ids,
    city_records=city_records,
    language=language,
)

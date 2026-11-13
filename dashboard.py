"""Аналитический дашборд исторической погоды и прогнозов."""

import base64
from pathlib import Path

import psycopg
import streamlit as st

from weather_analytics.dashboard.comparison import render_comparison_tab
from weather_analytics.dashboard.data import load_cities
from weather_analytics.dashboard.forecast import render_forecast_tab
from weather_analytics.dashboard.history import render_history_tab
from weather_analytics.localization import city_name, translate

# ---------------------------------------------------------
# Настройки страницы
# ---------------------------------------------------------

st.set_page_config(
    page_title='Weather Analytics',
    page_icon='🌍',
    layout='wide',
)

# ---------------------------------------------------------
# Настройки интерфейса
# ---------------------------------------------------------

selected_language = st.sidebar.selectbox(
    'Language / Язык',
    options=['Русский', 'English'],
    key='dashboard_language',
)

language = 'ru' if selected_language == 'Русский' else 'en'

# ---------------------------------------------------------
# Заголовок и Telegram-бот
# ---------------------------------------------------------

title_column, bot_column = st.columns(
    [5, 1],
    vertical_alignment='center',
)

with title_column:
    st.title('🌍 Weather Analytics')

with bot_column:
    stormy_path = Path(__file__).resolve().parent / 'assets' / 'stormy.png'

    if stormy_path.is_file():
        stormy_image = base64.b64encode(stormy_path.read_bytes()).decode('ascii')

        bot_title = (
            'Открыть Stormy в Telegram'
            if language == 'ru'
            else 'Open Stormy on Telegram'
        )
        bot_label = 'Открыть в Telegram ↗' if language == 'ru' else 'Open in Telegram ↗'

        st.markdown(
            f'''
            <div style="display:flex;justify-content:center;">
                <a href="https://t.me/StormyForecastBot"
                   target="_blank"
                   rel="noopener noreferrer"
                   title="{bot_title}"
                   aria-label="{bot_title}"
                   style="display:flex;flex-direction:column;
                          align-items:center;gap:5px;
                          text-decoration:none;text-align:center;">
                    <img src="data:image/png;base64,{stormy_image}"
                         alt="Stormy"
                         style="width:76px;height:76px;
                                border-radius:50%;object-fit:cover;
                                border:2px solid #4682B4;">
                    <span style="color:#4682B4;font-size:12px;
                                 font-weight:600;white-space:nowrap;">
                        {bot_label}
                    </span>
                </a>
            </div>
            ''',
            unsafe_allow_html=True,
        )
    else:
        st.link_button(
            'Telegram',
            'https://t.me/StormyForecastBot',
            icon=':material/send:',
            use_container_width=True,
        )

st.caption(translate('subtitle', language))

# ---------------------------------------------------------
# Загрузка городов
# ---------------------------------------------------------

try:
    cities = load_cities()
except psycopg.Error as error:
    st.error(f'{translate("db_error", language)}: {error}')
    st.stop()

if cities.empty:
    st.info(translate('no_data', language))
    st.stop()

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

# ---------------------------------------------------------
# Выбор города
# ---------------------------------------------------------

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
st.caption(f'{translate("timezone", language)}: {city_timezone}')

# ---------------------------------------------------------
# Переключатель разделов
# ---------------------------------------------------------

page_options = {
    'history': translate('history_tab', language),
    'forecast': translate('forecast_tab', language),
    'comparison': translate('compare_tab', language),
}

selected_page = st.segmented_control(
    ui_label := ('Раздел' if language == 'ru' else 'Section'),
    options=list(page_options),
    format_func=lambda page: page_options[page],
    default='history',
    selection_mode='single',
    key='dashboard_page',
    label_visibility='collapsed',
)

# ---------------------------------------------------------
# Отображаем только активный раздел
# ---------------------------------------------------------

if selected_page == 'history':
    render_history_tab(
        selected_city_id=selected_city_id,
        city_timezone=city_timezone,
        language=language,
    )

elif selected_page == 'forecast':
    render_forecast_tab(
        selected_city_id=selected_city_id,
        city_timezone=city_timezone,
        language=language,
    )

elif selected_page == 'comparison':
    render_comparison_tab(
        comparison_tab=st.container(),
        city_ids=city_ids,
        city_records=city_records,
        language=language,
    )

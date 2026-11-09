"""Общие погодные компоненты для истории и прогноза."""

import math
from datetime import UTC, datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st

from weather_analytics.dashboard.constants import (
    HEAT_ELEVATED_THRESHOLD,
    HEAT_HIGH_COLOR,
    HEAT_HIGH_THRESHOLD,
    HEAT_VERY_HIGH_COLOR,
    HEAT_VERY_HIGH_THRESHOLD,
    HPA_TO_MMHG,
    SAGE_GREEN,
    STEEL_BLUE,
    SYNODIC_MONTH_DAYS,
)


def ui(ru: str, en: str, language: str) -> str:
    """Возвращает локализованную подпись элемента интерфейса."""
    return ru if language == 'ru' else en


def wind_direction(degrees: float, language: str) -> str:
    """Преобразует направление ветра в один из восьми румбов."""
    if pd.isna(degrees):
        return '—'

    labels = (
        ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ']
        if language == 'ru'
        else ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    )

    return labels[int((float(degrees) % 360 + 22.5) // 45) % 8]


def heat_risk(
    apparent_temperature: float,
    language: str,
) -> tuple[str, str]:
    """Даёт ориентировочную категорию жары по ощущаемой температуре."""
    if apparent_temperature < HEAT_ELEVATED_THRESHOLD:
        return ui('Низкая', 'Low', language), SAGE_GREEN

    if apparent_temperature < HEAT_HIGH_THRESHOLD:
        return ui('Повышенная', 'Elevated', language), STEEL_BLUE

    if apparent_temperature < HEAT_VERY_HIGH_THRESHOLD:
        return ui('Высокая', 'High', language), HEAT_HIGH_COLOR

    return ui('Очень высокая', 'Very high', language), HEAT_VERY_HIGH_COLOR


def moon_phase(day, language: str) -> tuple[str, str, float]:
    """Приблизительно вычисляет фазу Луны по синодическому месяцу."""
    # Опорное новолуние: 6 января 2000 года, 18:14 UTC.
    reference = datetime(2000, 1, 6, 18, 14, tzinfo=UTC)
    moment = datetime.combine(day, datetime.min.time(), tzinfo=UTC)

    age = ((moment - reference) / timedelta(days=1)) % SYNODIC_MONTH_DAYS
    fraction = age / SYNODIC_MONTH_DAYS
    illumination = (1 - math.cos(2 * math.pi * fraction)) / 2 * 100

    names_ru = [
        'Новолуние',
        'Растущий серп',
        'Первая четверть',
        'Растущая Луна',
        'Полнолуние',
        'Убывающая Луна',
        'Последняя четверть',
        'Убывающий серп',
    ]

    names_en = [
        'New moon',
        'Waxing crescent',
        'First quarter',
        'Waxing gibbous',
        'Full moon',
        'Waning gibbous',
        'Last quarter',
        'Waning crescent',
    ]

    symbols = ['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘']
    index = int((fraction * 8 + 0.5) % 8)

    return (
        symbols[index],
        (names_ru if language == 'ru' else names_en)[index],
        illumination,
    )


def format_clock(value, timezone_name: str) -> str:
    """Отображает время восхода или заката в часовом поясе города."""
    if pd.isna(value):
        return '—'

    timestamp = pd.Timestamp(value)

    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(timezone_name)

    return timestamp.strftime('%H:%M')


def select_weather_day(
    dataframe: pd.DataFrame,
    date_column: str,
    language: str,
    key: str,
    label_ru: str,
    label_en: str,
):
    """Показывает календарь и возвращает выбранную доступную дату."""
    dates = (
        pd.to_datetime(
            dataframe[date_column],
            errors='coerce',
        )
        .dropna()
        .dt.date
    )

    if dates.empty:
        return None

    # Ограничиваем календарь диапазоном реально загруженных дат.
    available_dates = set(dates)
    earliest = min(available_dates)
    latest = max(available_dates)

    default_date = earliest if key.startswith('forecast') else latest

    # При переключении города или периода ранее выбранная дата
    # может оказаться за пределами нового диапазона.
    if key in st.session_state:
        current = st.session_state[key]

        if not isinstance(current, datetime) and current in available_dates:
            default_date = current

        if current not in available_dates:
            del st.session_state[key]

    selected = st.date_input(
        ui(label_ru, label_en, language),
        value=default_date,
        min_value=earliest,
        max_value=latest,
        format='DD.MM.YYYY',
        key=key,
    )

    # Календарь допускает выбор даты внутри диапазона,
    # даже если за конкретные сутки нет наблюдений.
    if selected not in available_dates:
        st.warning(
            ui(
                'За выбранную дату наблюдения отсутствуют. Выберите другую дату.',
                'No observations are available for this date. '
                'Please select another date.',
                language,
            )
        )
        return None

    return selected


def show_wind_compass(
    history: pd.DataFrame,
    language: str,
    date_column: str = 'weather_date',
    key: str = 'history_wind_compass_day',
) -> None:
    """Показывает направление и максимальную скорость ветра за выбранный день."""
    valid = history.dropna(subset=['wind_direction_dominant']).copy()

    if valid.empty:
        st.info(
            ui(
                'Нет данных о направлении ветра.',
                'No wind direction data.',
                language,
            )
        )
        return

    selected = select_weather_day(
        valid,
        date_column,
        language,
        key,
        'День для компаса',
        'Compass date',
    )

    if selected is None:
        return

    row = valid.loc[valid[date_column].dt.date == selected].iloc[0]

    direction = float(row['wind_direction_dominant']) % 360
    direction_label = wind_direction(direction, language)

    speed = row.get('wind_speed_max')
    speed_text = (
        f'{float(speed):.1f} {ui("км/ч", "km/h", language)}' if pd.notna(speed) else '—'
    )

    left, right = st.columns(
        [1, 2],
        vertical_alignment='center',
    )

    with left:
        # Компас статичен: сторонние графические библиотеки не нужны.
        compass_labels = (
            ('С', 'В', 'Ю', 'З') if language == 'ru' else ('N', 'E', 'S', 'W')
        )

        marks = ''.join(
            f'<line x1="110" y1="18" x2="110" y2="27" '
            f'transform="rotate({angle} 110 110)" '
            f'stroke="#7890A3" stroke-width="2"/>'
            for angle in range(0, 360, 30)
        )

        st.markdown(
            f'''
            <svg viewBox="0 0 220 220"
                 style="max-width:220px;width:100%;"
                 role="img"
                 aria-label="{escape(direction_label)} {direction:.0f}°">
                <circle cx="110" cy="110" r="91"
                        fill="none" stroke="#8EA7B7" stroke-width="2"/>
                <circle cx="110" cy="110" r="69"
                        fill="none" stroke="#A6B8C4"
                        stroke-dasharray="2 6"/>
                {marks}
                <text x="110" y="13" text-anchor="middle"
                      fill="#4682B4" font-size="14">{compass_labels[0]}</text>
                <text x="209" y="115" text-anchor="middle"
                      fill="#4682B4" font-size="14">{compass_labels[1]}</text>
                <text x="110" y="216" text-anchor="middle"
                      fill="#4682B4" font-size="14">{compass_labels[2]}</text>
                <text x="11" y="115" text-anchor="middle"
                      fill="#4682B4" font-size="14">{compass_labels[3]}</text>
                <g transform="rotate({direction:.2f} 110 110)">
                    <path d="M110 30 L100 78 L110 69 L120 78 Z"
                          fill="#4682B4"/>
                    <line x1="110" y1="77" x2="110" y2="156"
                          stroke="#4682B4" stroke-width="3"/>
                    <circle cx="110" cy="110" r="5" fill="#4682B4"/>
                </g>
                <rect x="76" y="93" width="68" height="36"
                      rx="10" fill="#E9F1F6"/>
                <text x="110" y="117" text-anchor="middle"
                      fill="#354E68" font-size="17" font-weight="bold">
                    {direction:.0f}°
                </text>
            </svg>
            ''',
            unsafe_allow_html=True,
        )

    with right:
        st.metric(
            ui('Направление ветра', 'Wind direction', language),
            f'{direction_label} ({direction:.0f}°)',
        )

        st.metric(
            ui(
                'Максимальная скорость за сутки',
                'Daily maximum wind speed',
                language,
            ),
            speed_text,
        )

        gusts = row.get('wind_gusts_max')

        if pd.notna(gusts):
            st.metric(
                ui(
                    'Максимальный порыв за сутки',
                    'Daily maximum wind gust',
                    language,
                ),
                f'{float(gusts):.1f} {ui("км/ч", "km/h", language)}',
            )

        st.caption(
            ui(
                'Стрелка указывает, откуда дует ветер. '
                'Показано преобладающее направление за выбранные сутки. '
                'Скорость и порывы — суточные максимумы.',
                'The arrow points to where the wind comes from. '
                'The prevailing direction for the selected day is shown. '
                'Wind speed and gusts are daily maxima.',
                language,
            )
        )


def show_sun_and_moon(
    history: pd.DataFrame,
    timezone_name: str,
    language: str,
    date_column: str = 'weather_date',
    key: str = 'history_sun_moon_day',
) -> None:
    """Показывает Солнце и фазу Луны за дату, выбранную в календаре."""
    if history.empty:
        st.info(
            ui(
                'Нет данных о Солнце и Луне.',
                'No sun and moon data.',
                language,
            )
        )
        return

    st.subheader(ui('Солнце', 'Sun', language))

    selected = select_weather_day(
        history,
        date_column,
        language,
        key,
        'День для солнца и Луны',
        'Sun and moon date',
    )

    if selected is None:
        return

    row = history.loc[history[date_column].dt.date == selected].iloc[0]

    sunrise = row.get('sunrise')
    sunset = row.get('sunset')
    duration = '—'

    # Open-Meteo возвращает daylight_duration в секундах.
    seconds = row.get('daylight_duration')

    if pd.notna(seconds):
        minutes = round(float(seconds) / 60)

        duration = (
            f'{minutes // 60} {ui("ч", "h", language)} '
            f'{minutes % 60:02d} {ui("мин", "min", language)}'
        )

    # Для истории продолжительность дня можно вычислить
    # по времени восхода и заката.
    if duration == '—' and pd.notna(sunrise) and pd.notna(sunset):
        minutes = round(
            (pd.Timestamp(sunset) - pd.Timestamp(sunrise)).total_seconds() / 60
        )

        if minutes >= 0:
            duration = (
                f'{minutes // 60} {ui("ч", "h", language)} '
                f'{minutes % 60:02d} {ui("мин", "min", language)}'
            )

    a, b, c = st.columns(3)

    a.metric(
        ui('Восход', 'Sunrise', language),
        format_clock(sunrise, timezone_name),
    )

    b.metric(
        ui('Закат', 'Sunset', language),
        format_clock(sunset, timezone_name),
    )

    c.metric(
        ui('Продолжительность дня', 'Day length', language),
        duration,
    )

    st.subheader(ui('Фаза Луны', 'Moon phase', language))

    symbol, phase, illumination = moon_phase(selected, language)

    left, right = st.columns(
        [1, 4],
        vertical_alignment='center',
    )

    with left:
        st.markdown(
            f'<div style="font-size:64px;text-align:center">{symbol}</div>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(f'**{phase}**')

        st.caption(
            f'{ui("Освещённость", "Illumination", language)}: ≈ {illumination:.0f}%'
        )

        st.caption(
            ui(
                'Приблизительный астрономический расчёт, не данные погодного API.',
                'Approximate astronomical calculation, not weather API data.',
                language,
            )
        )


def pressure_to_mmhg(values):
    """Переводит давление из гПа в мм рт. ст."""
    return pd.to_numeric(values, errors='coerce') * HPA_TO_MMHG

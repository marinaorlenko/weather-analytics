"""Интерфейс вкладки исторической погоды."""

import pandas as pd
import psycopg
import streamlit as st

from weather_analytics.dashboard.charts import (
    prepare_local_time,
    show_daily_chart,
    show_extra_charts,
    show_hourly_chart,
)
from weather_analytics.dashboard.constants import (
    DEEP_BLUE,
    HISTORY_DAILY_EXTRA,
    HISTORY_HOURLY_EXTRA,
    SAGE_GREEN,
    STEEL_BLUE,
)
from weather_analytics.dashboard.data import (
    load_extra_metrics,
    load_historical_daily,
    load_historical_daily_averages,
    load_historical_hourly,
)
from weather_analytics.dashboard.weather_ui import (
    heat_risk,
    show_sun_and_moon,
    show_wind_compass,
    ui,
    wind_direction,
)


def show_apparent_temperature(
    history: pd.DataFrame,
    extra_daily: pd.DataFrame,
    language: str,
) -> None:
    """Показывает ощущаемую температуру и ориентировочную категорию жары."""
    if (
        extra_daily.empty
        or 'apparent_temperature_mean' not in extra_daily
        or not extra_daily['apparent_temperature_mean'].notna().any()
    ):
        return

    st.subheader(
        ui(
            'Ощущаемая температура',
            'Feels-like temperature',
            language,
        )
    )

    # Сопоставляем среднюю фактическую и ощущаемую температуру по датам.
    dataframe = history[['weather_date', 'average_temperature']].merge(
        extra_daily[['weather_date', 'apparent_temperature_mean']],
        on='weather_date',
        how='inner',
    )

    dataframe = dataframe.dropna(subset=['apparent_temperature_mean'])

    if dataframe.empty:
        return

    # Показываем показатели для последнего дня выбранного периода.
    latest = dataframe.sort_values('weather_date').iloc[-1]

    apparent = float(latest['apparent_temperature_mean'])
    actual = latest['average_temperature']

    category, color = heat_risk(apparent, language)

    first, second, third = st.columns(3)

    first.metric(
        ui('Ощущается как', 'Feels like', language),
        f'{apparent:.1f} °C',
    )

    if pd.notna(actual):
        second.metric(
            ui('Средняя температура', 'Average temperature', language),
            f'{float(actual):.1f} °C',
            delta=f'{apparent - float(actual):+.1f} °C',
            delta_color='off',
        )
    else:
        second.metric(
            ui('Средняя температура', 'Average temperature', language),
            '—',
        )

    with third:
        st.markdown(f'**{ui("Тепловая нагрузка", "Heat stress", language)}**')
        st.markdown(
            f'<span style="color:{color};font-weight:600">{category}</span>',
            unsafe_allow_html=True,
        )

    st.caption(
        ui(
            'Показатели приведены для последнего дня выбранного периода. '
            'Категория жары ориентировочная и не является медицинской оценкой риска.',
            'Values refer to the last day in the selected period. '
            'Heat category is indicative, not a medical risk assessment.',
            language,
        )
    )


def show_precipitation(
    extra_daily: pd.DataFrame,
    language: str,
) -> None:
    """Показывает исторические дождь и снег при наличии данных."""
    st.subheader(
        ui(
            'Дождь и снег',
            'Rain and snowfall',
            language,
        )
    )

    if extra_daily.empty:
        st.info(
            ui(
                'Дополнительные данные об осадках отсутствуют.',
                'Additional precipitation data is unavailable.',
                language,
            )
        )
        return

    rain = (
        pd.to_numeric(
            extra_daily.get('rain_sum'),
            errors='coerce',
        )
        if 'rain_sum' in extra_daily
        else pd.Series(dtype=float)
    )

    snowfall = (
        pd.to_numeric(
            extra_daily.get('snowfall_sum'),
            errors='coerce',
        )
        if 'snowfall_sum' in extra_daily
        else pd.Series(dtype=float)
    )

    if not rain.notna().any() and not snowfall.notna().any():
        st.info(
            ui(
                'Нет данных о дожде и снеге за выбранный период.',
                'Rain and snowfall data is unavailable for the selected period.',
                language,
            )
        )
        return

    if not rain.gt(0).any() and not snowfall.gt(0).any():
        st.info(
            ui(
                'За выбранный период дождь и снег не зафиксированы.',
                'No rain or snowfall was recorded during the selected period.',
                language,
            )
        )
        return

    # Дождь и снег имеют разные единицы измерения.
    if rain.gt(0).any():
        show_daily_chart(
            extra_daily,
            'weather_date',
            ['rain_sum'],
            [ui('Дождь', 'Rain', language)],
            [STEEL_BLUE],
            ui('Осадки, мм', 'Precipitation, mm', language),
            language,
            chart_type='bar',
        )

    if snowfall.gt(0).any():
        show_daily_chart(
            extra_daily,
            'weather_date',
            ['snowfall_sum'],
            [ui('Снег', 'Snowfall', language)],
            [SAGE_GREEN],
            ui('Снег, см', 'Snowfall, cm', language),
            language,
            chart_type='bar',
        )


def render_history_tab(
    selected_city_id: int,
    city_timezone: str,
    language: str,
) -> None:
    """Отображает историческую погоду выбранного города."""
    try:
        daily = load_historical_daily(selected_city_id)

    except psycopg.Error as error:
        st.error(
            ui(
                f'Ошибка загрузки истории: {error}',
                f'Historical data loading error: {error}',
                language,
            )
        )
        return

    if daily.empty:
        st.info(
            ui(
                'Исторические данные пока отсутствуют.',
                'Historical data is not available yet.',
                language,
            )
        )
        return

    daily = daily.sort_values('weather_date').copy()

    # -----------------------------------------------------
    # Выбор периода
    # -----------------------------------------------------

    st.subheader(
        ui(
            'Период наблюдений',
            'Observation period',
            language,
        )
    )

    period_options = {
        'all': ui('Весь период', 'All available data', language),
        'last_7': ui('Последние 7 дней', 'Last 7 days', language),
        'last_30': ui('Последние 30 дней', 'Last 30 days', language),
        'last_365': ui('Последний год', 'Last year', language),
        'custom': ui('Выбрать даты', 'Custom dates', language),
    }

    period = st.selectbox(
        ui('Период', 'Period', language),
        options=list(period_options),
        format_func=lambda option: period_options[option],
        key='history_period',
    )

    earliest = daily['weather_date'].min().date()
    latest = daily['weather_date'].max().date()

    if period == 'last_7':
        start_date = max(
            earliest,
            latest - pd.Timedelta(days=6),
        )
        end_date = latest

    elif period == 'last_30':
        start_date = max(
            earliest,
            latest - pd.Timedelta(days=29),
        )
        end_date = latest

    elif period == 'last_365':
        start_date = max(
            earliest,
            latest - pd.Timedelta(days=364),
        )
        end_date = latest

    elif period == 'custom':
        selected_dates = st.date_input(
            ui('Диапазон дат', 'Date range', language),
            value=(earliest, latest),
            min_value=earliest,
            max_value=latest,
            key=f'history_custom_dates_{selected_city_id}',
        )

        if not isinstance(selected_dates, (tuple, list)) or len(selected_dates) != 2:
            st.info(
                ui(
                    'Выберите начальную и конечную даты.',
                    'Select the start and end dates.',
                    language,
                )
            )
            return

        start_date, end_date = selected_dates

    else:
        start_date = earliest
        end_date = latest

    history = daily.loc[
        daily['weather_date'].dt.date.between(
            start_date,
            end_date,
        )
    ].copy()

    if history.empty:
        st.info(
            ui(
                'За выбранный период данных нет.',
                'No data for the selected period.',
                language,
            )
        )
        return

        # -----------------------------------------------------
    # Среднесуточная температура
    # -----------------------------------------------------

    try:
        averages = load_historical_daily_averages(
            selected_city_id,
            city_timezone,
        )

        history = history.merge(
            averages,
            on='weather_date',
            how='left',
        )

    except psycopg.Error as error:
        st.error(
            ui(
                f'Ошибка загрузки средних температур: {error}',
                f'Average temperature loading error: {error}',
                language,
            )
        )
        history['average_temperature'] = float('nan')

    # -----------------------------------------------------
    # Сводные показатели
    # -----------------------------------------------------

    st.subheader(
        ui(
            'Основные показатели',
            'Key indicators',
            language,
        )
    )

    first, second, third, fourth = st.columns(4)

    first.metric(
        ui('Дней', 'Days', language),
        str(len(history)),
    )

    average_temperature = history['average_temperature'].mean()

    second.metric(
        ui('Средняя температура', 'Average temperature', language),
        (f'{average_temperature:.1f} °C' if pd.notna(average_temperature) else '—'),
    )

    precipitation_sum = history['precipitation'].sum(min_count=1)

    third.metric(
        ui('Всего осадков', 'Total precipitation', language),
        (
            f'{precipitation_sum:.1f} {ui("мм", "mm", language)}'
            if pd.notna(precipitation_sum)
            else '—'
        ),
    )

    maximum_wind = history['wind_speed_max'].max()

    fourth.metric(
        ui('Максимальный ветер', 'Maximum wind', language),
        (
            f'{maximum_wind:.1f} {ui("км/ч", "km/h", language)}'
            if pd.notna(maximum_wind)
            else '—'
        ),
    )

    # -----------------------------------------------------
    # Температура по дням
    # -----------------------------------------------------

    st.divider()
    st.subheader(
        ui(
            'Температура по дням',
            'Daily temperature',
            language,
        )
    )

    show_daily_chart(
        history,
        'weather_date',
        [
            'temperature_min',
            'average_temperature',
            'temperature_max',
        ],
        [
            ui('Минимум', 'Minimum', language),
            ui('Средняя', 'Average', language),
            ui('Максимум', 'Maximum', language),
        ],
        [
            DEEP_BLUE,
            STEEL_BLUE,
            SAGE_GREEN,
        ],
        '°C',
        language,
    )

    # -----------------------------------------------------
    # Дополнительные ежедневные показатели
    # -----------------------------------------------------

    try:
        extra_daily = load_extra_metrics(
            'historical_daily',
            selected_city_id,
            HISTORY_DAILY_EXTRA,
        )

    except psycopg.Error as error:
        st.error(
            ui(
                f'Ошибка дополнительных данных: {error}',
                f'Additional data loading error: {error}',
                language,
            )
        )
        extra_daily = pd.DataFrame()

    if not extra_daily.empty:
        extra_daily = extra_daily.loc[
            extra_daily['weather_date'].dt.date.between(
                start_date,
                end_date,
            )
        ].copy()

    st.divider()

    show_apparent_temperature(
        history,
        extra_daily,
        language,
    )

    show_precipitation(
        extra_daily,
        language,
    )

    # -----------------------------------------------------
    # Ветер и компас
    # -----------------------------------------------------

    st.divider()
    st.subheader(
        ui(
            'Ветер',
            'Wind',
            language,
        )
    )

    wind_history = history.copy()

    wind_history['wind_direction_label'] = wind_history[
        'wind_direction_dominant'
    ].apply(lambda degrees: wind_direction(degrees, language))

    show_daily_chart(
        wind_history,
        'weather_date',
        ['wind_speed_max'],
        [ui('Максимальная скорость', 'Maximum speed', language)],
        [STEEL_BLUE],
        ui('Скорость, км/ч', 'Speed, km/h', language),
        language,
    )

    show_wind_compass(
        history,
        language,
        date_column='weather_date',
        key='history_wind_compass_day',
    )

    if (
        not extra_daily.empty
        and 'wind_gusts_max' in extra_daily
        and extra_daily['wind_gusts_max'].notna().any()
    ):
        maximum_gust = extra_daily['wind_gusts_max'].max()

        st.metric(
            ui('Максимальный порыв', 'Maximum gust', language),
            f'{maximum_gust:.1f} {ui("км/ч", "km/h", language)}',
        )

    # -----------------------------------------------------
    # Почасовые наблюдения
    # -----------------------------------------------------

    st.divider()
    st.subheader(
        ui(
            'Почасовые наблюдения',
            'Hourly observations',
            language,
        )
    )

    try:
        hourly = load_historical_hourly(
            selected_city_id,
            str(start_date),
            str(end_date),
            city_timezone,
        )

    except psycopg.Error as error:
        st.error(
            ui(
                f'Ошибка почасовых данных: {error}',
                f'Hourly data loading error: {error}',
                language,
            )
        )
        hourly = pd.DataFrame()

    if not hourly.empty:
        hourly = prepare_local_time(
            hourly,
            'weather_time',
            city_timezone,
        )

        show_hourly_chart(
            hourly,
            'temperature',
            ui('Температура по часам', 'Hourly temperature', language),
            STEEL_BLUE,
            '°C',
            language,
        )

        show_hourly_chart(
            hourly,
            'humidity',
            ui('Влажность по часам', 'Hourly humidity', language),
            SAGE_GREEN,
            '%',
            language,
        )

    # -----------------------------------------------------
    # Дополнительные почасовые показатели
    # -----------------------------------------------------

    try:
        extra_hourly = load_extra_metrics(
            'historical_hourly',
            selected_city_id,
            HISTORY_HOURLY_EXTRA,
        )

    except psycopg.Error as error:
        st.error(
            ui(
                f'Ошибка дополнительных почасовых данных: {error}',
                f'Additional hourly data loading error: {error}',
                language,
            )
        )
        extra_hourly = pd.DataFrame()

    if not extra_hourly.empty:
        local_dates = extra_hourly['weather_time'].dt.tz_convert(city_timezone).dt.date

        extra_hourly = extra_hourly.loc[
            local_dates.between(start_date, end_date)
        ].copy()

    if not extra_hourly.empty:
        st.divider()
        st.subheader(
            ui(
                'Дополнительные почасовые показатели',
                'Additional hourly metrics',
                language,
            )
        )

        show_extra_charts(
            extra_hourly,
            'weather_time',
            (
                'dew_point',
                'wind_gusts',
                'cloud_cover',
                'pressure_msl',
            ),
            language,
            city_timezone,
        )

    # -----------------------------------------------------
    # Солнце и Луна
    # -----------------------------------------------------

    st.divider()

    show_sun_and_moon(
        history,
        city_timezone,
        language,
        date_column='weather_date',
        key='history_sun_moon_day',
    )

    # -----------------------------------------------------
    # Исходные данные
    # -----------------------------------------------------

    with st.expander(
        ui(
            'Исходные исторические данные',
            'Historical source data',
            language,
        )
    ):
        st.markdown(f'**{ui("По дням", "Daily", language)}**')
        st.dataframe(
            history,
            hide_index=True,
            width='stretch',
        )

        if not hourly.empty:
            st.markdown(f'**{ui("По часам", "Hourly", language)}**')
            st.dataframe(
                hourly,
                hide_index=True,
                width='stretch',
            )

            st.caption(
                f'{ui("Почасовых записей", "Hourly records", language)}: {len(hourly)}'
            )

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
    HISTORY_DAILY_EXTRA,
    HISTORY_HOURLY_EXTRA,
    LIGHT_CORAL,
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


def aggregate_daily_data(
    dataframe: pd.DataFrame,
    aggregations: dict[str, str],
    date_column: str = 'weather_date',
) -> pd.DataFrame:
    """Агрегирует дневные данные для графиков длительных периодов."""
    if dataframe.empty:
        return dataframe.copy()

    dates = pd.to_datetime(dataframe[date_column])
    period_days = (dates.max() - dates.min()).days + 1

    # Для коротких периодов сохраняем каждое дневное наблюдение.
    if period_days <= 90:
        return dataframe.copy()

    # До двух лет отображаем месяцы, для более длинных периодов — годы.
    frequency = 'MS' if period_days <= 730 else 'YS'

    available = {
        column: method
        for column, method in aggregations.items()
        if column in dataframe.columns
    }

    if not available:
        return pd.DataFrame(columns=[date_column, *aggregations])

    result = dataframe[[date_column, *available]].copy()
    result[date_column] = pd.to_datetime(result[date_column])

    # При суммировании осадков сохраняем NaN,
    # если за весь месяц или год нет ни одного наблюдения.
    available = {
        column: (
            (lambda values: values.sum(min_count=1)) if method == 'sum' else method
        )
        for column, method in available.items()
    }

    # Группируем по календарным месяцам или годам.
    # Каждому показателю соответствует собственный метод агрегации.
    result = (
        result.set_index(date_column).resample(frequency).agg(available).reset_index()
    )

    # Не показываем интервалы, в которых отсутствуют все показатели.
    return result.dropna(subset=list(available), how='all')


def select_hourly_period(
    start_date,
    end_date,
    language: str,
    city_id: int,
) -> tuple | None:
    """Позволяет выбрать до 14 дней почасовых наблюдений через календарь."""
    st.subheader(
        ui(
            'Период почасовых наблюдений',
            'Hourly observation period',
            language,
        )
    )

    default_start = max(
        start_date,
        end_date - pd.Timedelta(days=6),
    )
    default_period = (default_start, end_date)

    key = f'history_hourly_dates_{city_id}'

    # Сбрасываем сохранённый диапазон только при смене доступных границ.
    # Неполный выбор и период длиннее 14 дней не сбрасываем:
    # пользователь должен иметь возможность завершить или исправить ввод.
    if key in st.session_state:
        current = st.session_state[key]
        if not isinstance(current, (tuple, list)):
            del st.session_state[key]
        elif any(day < start_date or day > end_date for day in current):
            del st.session_state[key]

    selected = st.date_input(
        ui(
            'Выберите даты (не более 14 дней)',
            'Select dates (maximum 14 days)',
            language,
        ),
        value=default_period,
        min_value=start_date,
        max_value=end_date,
        format='DD.MM.YYYY',
        key=key,
    )

    if not isinstance(selected, (tuple, list)) or len(selected) != 2:
        st.info(
            ui(
                'Выберите начальную и конечную даты.',
                'Select the start and end dates.',
                language,
            )
        )
        return None

    hourly_start, hourly_end = selected

    if (hourly_end - hourly_start).days >= 14:
        st.warning(
            ui(
                'Выбран период более 14 дней. Укажите интервал не более '
                '14 календарных дней. Графики обновятся после исправления дат.',
                'The selected period exceeds 14 days. Choose a range of up to '
                '14 calendar days. Charts will update after the dates are corrected.',
                language,
            )
        )
        return None

    return hourly_start, hourly_end


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

    # Рассчитываем средние значения по дням с доступной ощущаемой
    # температурой, чтобы сравнение использовало один и тот же набор дат.
    apparent = float(dataframe['apparent_temperature_mean'].mean())
    actual = dataframe['average_temperature'].mean()

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
            'Показаны средние значения за дни выбранного периода, для которых '
            'доступна ощущаемая температура. Категория тепловой нагрузки '
            'по среднему значению ориентировочная и не является медицинской '
            'оценкой риска.',
            'Averages cover days in the selected period with available '
            'feels-like '
            'temperature data. Heat stress based on the period average is '
            'indicative and is not a medical risk assessment.',
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

    # Для месячных и годовых графиков осадки суммируются.
    chart_data = aggregate_daily_data(
        extra_daily,
        {
            'rain_sum': 'sum',
            'snowfall_sum': 'sum',
        },
    )

    if rain.gt(0).any():
        show_daily_chart(
            chart_data,
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
            chart_data,
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
    # Выбор основного периода
    # -----------------------------------------------------

    period_options = {
        'all': ui('Весь период', 'All available data', language),
        'last_7': ui('Последние 7 дней', 'Last 7 days', language),
        'last_30': ui('Последние 30 дней', 'Last 30 days', language),
        'last_365': ui('Последний год', 'Last year', language),
        'custom': ui('Выбрать даты', 'Custom dates', language),
    }

    # Сохраняем выбранный период независимо от языка интерфейса.
    if 'history_period_value' not in st.session_state:
        st.session_state.history_period_value = 'all'

    period = st.sidebar.selectbox(
        ui('Период', 'Period', language),
        options=list(period_options),
        index=list(period_options).index(st.session_state.history_period_value),
        format_func=lambda option: period_options[option],
        key=f'history_period_{language}',
    )

    st.session_state.history_period_value = period

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
        selected_dates = st.sidebar.date_input(
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
    # Температура по дням, месяцам или годам
    # -----------------------------------------------------

    st.divider()
    st.subheader(
        ui(
            'Температура',
            'Temperature',
            language,
        )
    )

    temperature_chart = aggregate_daily_data(
        history,
        {
            'temperature_min': 'min',
            'average_temperature': 'mean',
            'temperature_max': 'max',
        },
    )

    show_daily_chart(
        temperature_chart,
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
            LIGHT_CORAL,
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

    wind_chart = aggregate_daily_data(
        wind_history,
        {'wind_speed_max': 'max'},
    )

    show_daily_chart(
        wind_chart,
        'weather_date',
        ['wind_speed_max'],
        [ui('Максимальная скорость', 'Maximum speed', language)],
        [STEEL_BLUE],
        ui('Скорость, км/ч', 'Speed, km/h', language),
        language,
    )

    show_wind_compass(
        daily,
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
    # Выбор периода почасовых наблюдений
    # -----------------------------------------------------

    st.divider()

    hourly_period = select_hourly_period(
        earliest,
        latest,
        language,
        selected_city_id,
    )

    hourly = pd.DataFrame()
    extra_hourly = pd.DataFrame()

    if hourly_period is not None:
        hourly_start, hourly_end = hourly_period

        # -----------------------------------------------------
        # Почасовые наблюдения
        # -----------------------------------------------------

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
                str(hourly_start),
                str(hourly_end),
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
        else:
            st.info(
                ui(
                    'За выбранный почасовой период наблюдений нет.',
                    'No hourly observations for the selected period.',
                    language,
                )
            )

    if hourly_period is not None:
        # -----------------------------------------------------
        # Дополнительные почасовые показатели
        # -----------------------------------------------------

        try:
            extra_hourly = load_extra_metrics(
                'historical_hourly',
                selected_city_id,
                HISTORY_HOURLY_EXTRA,
                start_date=str(hourly_start),
                end_date=str(hourly_end),
                timezone=city_timezone,
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
        daily,
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

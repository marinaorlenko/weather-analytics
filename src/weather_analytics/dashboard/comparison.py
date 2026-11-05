"""Интерфейс вкладки сравнения исторической погоды городов."""

import altair as alt
import pandas as pd
import psycopg
import streamlit as st

from weather_analytics.dashboard.charts import get_date_ticks
from weather_analytics.dashboard.constants import (
    SAGE_GREEN,
    STEEL_BLUE,
)
from weather_analytics.dashboard.data import (
    load_historical_daily,
    load_historical_daily_averages,
)
from weather_analytics.dashboard.weather_ui import ui
from weather_analytics.localization import city_name, translate

METRICS = {
    'average_temperature': {
        'ru': 'Средняя температура',
        'en': 'Average temperature',
        'unit': '°C',
        'chart_type': 'line',
    },
    'temperature_min': {
        'ru': 'Минимальная температура',
        'en': 'Minimum temperature',
        'unit': '°C',
        'chart_type': 'line',
    },
    'temperature_max': {
        'ru': 'Максимальная температура',
        'en': 'Maximum temperature',
        'unit': '°C',
        'chart_type': 'line',
    },
    'precipitation': {
        'ru': 'Осадки',
        'en': 'Precipitation',
        'unit': {'ru': 'мм', 'en': 'mm'},
        'chart_type': 'bar',
    },
    'wind_speed_max': {
        'ru': 'Максимальная скорость ветра',
        'en': 'Maximum wind speed',
        'unit': {'ru': 'км/ч', 'en': 'km/h'},
        'chart_type': 'line',
    },
}


def load_comparison_history(
    city_id: int,
    timezone_name: str,
) -> pd.DataFrame:
    """Загружает и объединяет исторические показатели города."""
    daily = load_historical_daily(city_id)

    if daily.empty:
        return pd.DataFrame()

    averages = load_historical_daily_averages(
        city_id,
        timezone_name,
    )

    # Среднесуточная температура рассчитывается из почасовых данных.
    # Остальные показатели уже содержатся в ежедневной таблице.
    if not averages.empty:
        daily = daily.merge(
            averages[['weather_date', 'average_temperature']],
            on='weather_date',
            how='left',
        )
    else:
        daily['average_temperature'] = float('nan')

    daily['weather_date'] = pd.to_datetime(
        daily['weather_date'],
        errors='coerce',
    ).dt.normalize()

    return daily.dropna(
        subset=['weather_date']
    ).sort_values('weather_date')


def prepare_comparison(
    first_history: pd.DataFrame,
    second_history: pd.DataFrame,
) -> pd.DataFrame:
    """Оставляет только календарные даты, общие для двух городов."""
    columns = ['weather_date', *METRICS]

    first = first_history[columns].copy()
    second = second_history[columns].copy()

    # Суффиксы сохраняют принадлежность каждого показателя городу.
    comparison = first.merge(
        second,
        on='weather_date',
        how='inner',
        suffixes=('_first', '_second'),
        validate='one_to_one',
    )

    return comparison.sort_values(
        'weather_date'
    ).reset_index(drop=True)


def show_comparison_kpis(
    comparison: pd.DataFrame,
    first_label: str,
    second_label: str,
    language: str,
) -> None:
    """Показывает сводные показатели за общий период наблюдений."""
    st.subheader(ui(
        'Сводные показатели',
        'Summary indicators',
        language,
    ))

    temperature_data = comparison[
        ['average_temperature_first', 'average_temperature_second']
    ].dropna()

    first_temperature = temperature_data[
        'average_temperature_first'
    ].mean()

    second_temperature = temperature_data[
        'average_temperature_second'
    ].mean()

    temperature_difference = (
        first_temperature - second_temperature
    )

    # Для разницы используем только даты, когда известны
    # обе среднесуточные температуры.
    temperature_difference = (
        comparison['average_temperature_first']
        - comparison['average_temperature_second']
    ).mean()

    first_precipitation = comparison[
        'precipitation_first'
    ].sum(min_count=1)

    second_precipitation = comparison[
        'precipitation_second'
    ].sum(min_count=1)

    first_wind = comparison[
        'wind_speed_max_first'
    ].max()

    second_wind = comparison[
        'wind_speed_max_second'
    ].max()

    first_column, second_column, third_column = st.columns(3)

    with first_column:
        st.metric(
            ui('Средняя температура', 'Average temperature', language),
            (
                f'{first_temperature:.1f} °C'
                if pd.notna(first_temperature)
                else '—'
            ),
        )
        st.caption(first_label)

    with second_column:
        st.metric(
            ui('Средняя температура', 'Average temperature', language),
            (
                f'{second_temperature:.1f} °C'
                if pd.notna(second_temperature)
                else '—'
            ),
        )
        st.caption(second_label)

    with third_column:
        st.metric(
            ui('Разница температур', 'Temperature difference', language),
            (
                f'{temperature_difference:+.1f} °C'
                if pd.notna(temperature_difference)
                else '—'
            ),
        )
        st.caption(ui(
            'Первый город относительно второго',
            'First city relative to second',
            language,
        ))

    st.divider()

    first_column, second_column = st.columns(2)

    with first_column:
        st.markdown(
            f'**{ui("Суммарные осадки", "Total precipitation", language)}**'
        )

        st.metric(
            first_label,
            (
                f'{first_precipitation:.1f} мм'
                if pd.notna(first_precipitation)
                else '—'
            ),
        )

        st.metric(
            second_label,
            (
                f'{second_precipitation:.1f} мм'
                if pd.notna(second_precipitation)
                else '—'
            ),
        )

    with second_column:
        st.markdown(
            f'**{ui("Максимальный ветер", "Maximum wind", language)}**'
        )

        st.metric(
            first_label,
            (
                f'{first_wind:.1f} км/ч'
                if pd.notna(first_wind)
                else '—'
            ),
        )

        st.metric(
            second_label,
            (
                f'{second_wind:.1f} км/ч'
                if pd.notna(second_wind)
                else '—'
            ),
        )

    st.caption(
        f'{ui("Общих дней наблюдений", "Common observation days", language)}: '
        f'{len(comparison)}'
    )


def show_metric_comparison(
    comparison: pd.DataFrame,
    metric: str,
    first_label: str,
    second_label: str,
    language: str,
) -> None:
    """Сравнивает выбранный погодный показатель двух городов."""
    settings = METRICS[metric]
    label = settings[language]

    # Выбираем единицу измерения для текущего языка интерфейса.
    unit_settings = settings['unit']
    unit = (
        unit_settings[language]
        if isinstance(unit_settings, dict)
        else unit_settings
    )

    first_column = f'{metric}_first'
    second_column = f'{metric}_second'

    chart_data = comparison[
        ['weather_date', first_column, second_column]
    ].melt(
        id_vars='weather_date',
        value_vars=[first_column, second_column],
        var_name='city',
        value_name='value',
    ).dropna(subset=['value'])

    if chart_data.empty:
        st.info(ui(
            'Нет данных для выбранного показателя.',
            'No data for the selected indicator.',
            language,
        ))
        return

    chart_data['city'] = chart_data['city'].map({
        first_column: first_label,
        second_column: second_label,
    })

    chart_data['date_label'] = (
        chart_data['weather_date']
        .dt.strftime('%d.%m.%Y')
    )

    ticks = get_date_ticks(comparison, 'weather_date')

    base = alt.Chart(chart_data).encode(
        x=alt.X(
            'weather_date:T',
            title=ui('Дата', 'Date', language),
            axis=alt.Axis(
                values=ticks,
                format='%d.%m',
                labelAngle=0,
                grid=True,
            ),
        ),
        y=alt.Y(
            'value:Q',
            title=f'{label}, {unit}',
            scale=alt.Scale(
                zero=True,
            ),
        ),
        color=alt.Color(
            'city:N',
            scale=alt.Scale(
                domain=[first_label, second_label],
                range=[STEEL_BLUE, SAGE_GREEN],
            ),
            legend=alt.Legend(title=None),
        ),
        tooltip=[
            alt.Tooltip(
                'date_label:N',
                title=ui('Дата', 'Date', language),
            ),
            alt.Tooltip(
                'city:N',
                title=ui('Город', 'City', language),
            ),
            alt.Tooltip(
                'value:Q',
                title=f'{label}, {unit}',
                format='.1f',
            ),
        ],
    )

    if settings['chart_type'] == 'bar':
        chart = base.mark_bar().encode(
            xOffset=alt.XOffset(
                'city:N',
                sort=[first_label, second_label],
            ),
        )
    else:
        chart = base.mark_line(
            point=True,
            strokeWidth=2.5,
        )

    st.altair_chart(
        chart.properties(height=360),
        width='stretch',
    )


def render_comparison_tab(
    comparison_tab,
    city_ids: list[int],
    city_records: dict,
    language: str,
) -> None:
    """Отображает аналитическое сравнение двух городов."""
    with comparison_tab:
        st.header(translate('compare', language))

        if len(city_ids) < 2:
            st.info(translate('need_cities', language))
            return

        # Сохраняем выбор городов при смене языка.
        if (
            st.session_state.get('current_first_city_id')
            not in city_ids
        ):
            st.session_state.current_first_city_id = city_ids[0]

        if (
            st.session_state.get('current_second_city_id')
            not in city_ids
        ):
            st.session_state.current_second_city_id = city_ids[1]

        first_column, second_column = st.columns(2)

        with first_column:
            first_city_id = st.selectbox(
                translate('first_city', language),
                options=city_ids,
                index=city_ids.index(
                    st.session_state.current_first_city_id
                ),
                format_func=lambda city_id: city_name(
                    city_records[city_id]['name'],
                    city_records[city_id]['country'],
                    language,
                ),
                key=f'compare_first_city_{language}',
            )

        with second_column:
            second_city_id = st.selectbox(
                translate('second_city', language),
                options=city_ids,
                index=city_ids.index(
                    st.session_state.current_second_city_id
                ),
                format_func=lambda city_id: city_name(
                    city_records[city_id]['name'],
                    city_records[city_id]['country'],
                    language,
                ),
                key=f'compare_second_city_{language}',
            )

        st.session_state.current_first_city_id = first_city_id
        st.session_state.current_second_city_id = second_city_id

        if first_city_id == second_city_id:
            st.info(translate('same_city', language))
            return

        first_city = city_records[first_city_id]
        second_city = city_records[second_city_id]

        first_label = city_name(
            first_city['name'],
            first_city['country'],
            language,
        )

        second_label = city_name(
            second_city['name'],
            second_city['country'],
            language,
        )

        try:
            first_history = load_comparison_history(
                first_city_id,
                first_city['timezone'],
            )

            second_history = load_comparison_history(
                second_city_id,
                second_city['timezone'],
            )

        except psycopg.Error as error:
            st.error(
                f'{translate("db_error", language)}: {error}'
            )
            return

        if first_history.empty or second_history.empty:
            st.info(translate('need_history', language))
            return

        comparison = prepare_comparison(
            first_history,
            second_history,
        )

        if comparison.empty:
            st.info(ui(
                'У выбранных городов нет общих дат наблюдений.',
                'The selected cities have no common observation dates.',
                language,
            ))
            return

        # -------------------------------------------------
        # Выбор общего периода
        # -------------------------------------------------

        st.subheader(ui(
            'Период сравнения',
            'Comparison period',
            language,
        ))

        earliest = comparison['weather_date'].min().date()
        latest = comparison['weather_date'].max().date()

        selected_dates = st.date_input(
            ui('Диапазон дат', 'Date range', language),
            value=(earliest, latest),
            min_value=earliest,
            max_value=latest,
            key='comparison_date_range',
        )

        if not isinstance(selected_dates, (tuple, list)):
            return

        if len(selected_dates) != 2:
            st.info(ui(
                'Выберите начальную и конечную даты.',
                'Select the start and end dates.',
                language,
            ))
            return

        start_date, end_date = selected_dates

        comparison = comparison.loc[
            comparison['weather_date'].dt.date.between(
                start_date,
                end_date,
            )
        ].copy()

        if comparison.empty:
            st.info(ui(
                'За выбранный период нет общих наблюдений.',
                'No common observations in the selected period.',
                language,
            ))
            return

        # -------------------------------------------------
        # Сравнительные KPI
        # -------------------------------------------------

        show_comparison_kpis(
            comparison,
            first_label,
            second_label,
            language,
        )

        # -------------------------------------------------
        # График выбранного показателя
        # -------------------------------------------------

        st.divider()
        st.subheader(ui(
            'Сравнение погодных показателей',
            'Weather indicator comparison',
            language,
        ))

        selected_metric = st.selectbox(
            ui('Показатель', 'Indicator', language),
            options=list(METRICS),
            format_func=lambda metric: METRICS[metric][language],
            key='comparison_metric',
        )

        show_metric_comparison(
            comparison,
            selected_metric,
            first_label,
            second_label,
            language,
        )

        # -------------------------------------------------
        # Исходные данные
        # -------------------------------------------------

        with st.expander(ui(
            'Данные сравнения',
            'Comparison data',
            language,
        )):
            st.dataframe(
                comparison,
                hide_index=True,
                width='stretch',
            )

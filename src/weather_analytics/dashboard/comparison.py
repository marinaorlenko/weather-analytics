"""Интерфейс сравнения исторической погоды двух городов."""

import altair as alt
import pandas as pd
import psycopg
import streamlit as st

from weather_analytics.dashboard.charts import get_date_format, get_date_ticks
from weather_analytics.dashboard.constants import SAGE_GREEN, STEEL_BLUE
from weather_analytics.dashboard.data import (
    load_comparison_hourly_averages,
    load_extra_metrics,
    load_historical_daily,
    load_historical_daily_averages,
)
from weather_analytics.dashboard.weather_ui import pressure_to_mmhg, ui
from weather_analytics.localization import city_name, translate

METRICS = {
    'average_temperature': {
        'ru': 'Средняя температура',
        'en': 'Average temperature',
        'unit': '°C',
        'aggregation': 'mean',
        'chart_type': 'line',
    },
    'temperature_min': {
        'ru': 'Минимальная температура',
        'en': 'Minimum temperature',
        'unit': '°C',
        'aggregation': 'mean',
        'chart_type': 'line',
    },
    'temperature_max': {
        'ru': 'Максимальная температура',
        'en': 'Maximum temperature',
        'unit': '°C',
        'aggregation': 'mean',
        'chart_type': 'line',
    },
    'precipitation': {
        'ru': 'Осадки',
        'en': 'Precipitation',
        'unit': 'мм',
        'aggregation': 'sum',
        'chart_type': 'bar',
    },
    'wind_speed_max': {
        'ru': 'Максимальная скорость ветра',
        'en': 'Maximum wind speed',
        'unit': 'км/ч',
        'aggregation': 'max',
        'chart_type': 'line',
    },
    'wind_gusts_max': {
        'ru': 'Максимальные порывы ветра',
        'en': 'Maximum wind gusts',
        'unit': 'км/ч',
        'aggregation': 'max',
        'chart_type': 'line',
    },
    'humidity': {
        'ru': 'Относительная влажность',
        'en': 'Relative humidity',
        'unit': '%',
        'aggregation': 'mean',
        'chart_type': 'line',
    },
    'dew_point': {
        'ru': 'Точка росы',
        'en': 'Dew point',
        'unit': '°C',
        'aggregation': 'mean',
        'chart_type': 'line',
    },
    'cloud_cover': {
        'ru': 'Облачность',
        'en': 'Cloud cover',
        'unit': '%',
        'aggregation': 'mean',
        'chart_type': 'line',
    },
    'pressure_msl': {
        'ru': 'Атмосферное давление',
        'en': 'Atmospheric pressure',
        'unit': 'мм рт. ст.',
        'aggregation': 'mean',
        'chart_type': 'line',
    },
    'daylight_hours': {
        'ru': 'Продолжительность светового дня',
        'en': 'Daylight duration',
        'unit': 'ч',
        'aggregation': 'mean',
        'chart_type': 'line',
    },
}

PERIODS = {
    'all': ('Весь период', 'All time'),
    '7d': ('Последние 7 дней', 'Last 7 days'),
    '30d': ('Последние 30 дней', 'Last 30 days'),
    'year': ('Последний год', 'Last year'),
    'custom': ('Произвольный период', 'Custom period'),
}

CITY_COLORS = (STEEL_BLUE, SAGE_GREEN)


def load_comparison_history(
    city_id: int,
    timezone_name: str,
) -> pd.DataFrame:
    """Объединяет исторические показатели одного города по местным датам."""
    daily = load_historical_daily(city_id)

    if daily.empty:
        return pd.DataFrame()

    daily = daily.copy()
    daily['weather_date'] = pd.to_datetime(
        daily['weather_date'],
        errors='coerce',
    ).dt.normalize()

    daily = daily.dropna(subset=['weather_date'])

    averages = load_historical_daily_averages(
        city_id,
        timezone_name,
    )

    if not averages.empty:
        daily = daily.merge(
            averages[['weather_date', 'average_temperature']],
            on='weather_date',
            how='left',
            validate='one_to_one',
        )
    else:
        daily['average_temperature'] = float('nan')

    gusts = load_extra_metrics(
        'historical_daily',
        city_id,
        ('wind_gusts_max',),
    )

    if not gusts.empty:
        gusts['weather_date'] = pd.to_datetime(
            gusts['weather_date'],
            errors='coerce',
        ).dt.normalize()

        daily = daily.merge(
            gusts,
            on='weather_date',
            how='left',
            validate='one_to_one',
        )
    else:
        daily['wind_gusts_max'] = float('nan')

    hourly = load_comparison_hourly_averages(
        city_id,
        timezone_name,
    )

    hourly_columns = (
        'humidity',
        'dew_point',
        'cloud_cover',
        'pressure_msl',
    )

    if not hourly.empty:
        daily = daily.merge(
            hourly,
            on='weather_date',
            how='left',
            validate='one_to_one',
        )
    else:
        for column in hourly_columns:
            daily[column] = float('nan')

    # SQL-загрузчик возвращает давление в гПа.
    # Для сравнения используем те же единицы, что и в истории.
    daily['pressure_msl'] = pressure_to_mmhg(daily['pressure_msl'])

    # Восход и закат — моменты времени. Их разность
    # корректно рассчитывается независимо от часового пояса.
    sunrise = pd.to_datetime(
        daily['sunrise'],
        errors='coerce',
        utc=True,
    )
    sunset = pd.to_datetime(
        daily['sunset'],
        errors='coerce',
        utc=True,
    )

    daylight = (sunset - sunrise).dt.total_seconds() / 3600

    daily['daylight_hours'] = daylight.where(daylight.between(0, 24))

    for metric in METRICS:
        daily[metric] = pd.to_numeric(
            daily[metric],
            errors='coerce',
        )

    return daily.sort_values('weather_date').reset_index(drop=True)


def prepare_comparison(
    first_history: pd.DataFrame,
    second_history: pd.DataFrame,
) -> pd.DataFrame:
    """Объединяет показатели городов по общим календарным датам."""
    columns = ['weather_date', *METRICS]

    first = first_history[columns].copy()
    second = second_history[columns].copy()

    comparison = first.merge(
        second,
        on='weather_date',
        how='inner',
        suffixes=('_first', '_second'),
        validate='one_to_one',
    )

    return comparison.sort_values('weather_date').reset_index(drop=True)


def select_comparison_period(
    comparison: pd.DataFrame,
    language: str,
) -> pd.DataFrame:
    """Выбирает общий период наблюдений через боковую панель."""
    earliest = comparison['weather_date'].min().date()
    latest = comparison['weather_date'].max().date()

    selected_period = st.sidebar.selectbox(
        ui('Период', 'Period', language),
        options=list(PERIODS),
        format_func=lambda value: PERIODS[value][0 if language == 'ru' else 1],
        key='comparison_period',
    )

    if selected_period == '7d':
        start_date = max(
            earliest,
            (pd.Timestamp(latest) - pd.Timedelta(days=6)).date(),
        )
        end_date = latest

    elif selected_period == '30d':
        start_date = max(
            earliest,
            (pd.Timestamp(latest) - pd.Timedelta(days=29)).date(),
        )
        end_date = latest

    elif selected_period == 'year':
        start_date = max(
            earliest,
            (pd.Timestamp(latest) - pd.DateOffset(years=1)).date(),
        )
        end_date = latest

    elif selected_period == 'custom':
        selected_dates = st.sidebar.date_input(
            ui('Диапазон дат', 'Date range', language),
            value=(earliest, latest),
            min_value=earliest,
            max_value=latest,
            key='comparison_custom_dates',
        )

        if not isinstance(selected_dates, (tuple, list)) or len(selected_dates) != 2:
            st.info(
                ui(
                    'Выберите начальную и конечную даты.',
                    'Select the start and end dates.',
                    language,
                )
            )
            return comparison.iloc[0:0].copy()

        start_date, end_date = selected_dates

    else:
        start_date, end_date = earliest, latest

    st.sidebar.caption(f'{start_date:%d.%m.%Y} — {end_date:%d.%m.%Y}')

    return comparison.loc[
        comparison['weather_date'].dt.date.between(
            start_date,
            end_date,
        )
    ].copy()


def paired_metric_data(
    comparison: pd.DataFrame,
    metric: str,
) -> pd.DataFrame:
    """Оставляет только даты с данными показателя у обоих городов."""
    first_column = f'{metric}_first'
    second_column = f'{metric}_second'

    return (
        comparison[['weather_date', first_column, second_column]]
        .dropna(subset=[first_column, second_column])
        .copy()
    )


def calculate_metric(
    dataframe: pd.DataFrame,
    column: str,
    aggregation: str,
) -> float:
    """Рассчитывает показатель по имеющимся значениям."""
    values = pd.to_numeric(
        dataframe[column],
        errors='coerce',
    ).dropna()

    if values.empty:
        return float('nan')

    if aggregation == 'sum':
        return float(values.sum())

    if aggregation == 'max':
        return float(values.max())

    return float(values.mean())


def show_city_kpis(
    comparison: pd.DataFrame,
    city_label: str,
    suffix: str,
    color: str,
    language: str,
) -> None:
    """Показывает KPI города под крупным заголовком."""
    st.markdown(
        f'<div style="height:4px;background:{color};'
        'border-radius:4px;margin-bottom:12px;"></div>',
        unsafe_allow_html=True,
    )

    st.subheader(city_label)

    indicators = (
        ('average_temperature', 'mean'),
        ('precipitation', 'sum'),
        ('wind_speed_max', 'max'),
        ('humidity', 'mean'),
    )

    for metric, aggregation in indicators:
        data = paired_metric_data(comparison, metric)
        value = calculate_metric(
            data,
            f'{metric}_{suffix}',
            aggregation,
        )

        settings = METRICS[metric]
        formatted = f'{value:.1f} {settings["unit"]}' if pd.notna(value) else '—'

        st.metric(
            settings[language],
            formatted,
        )


def show_comparison_kpis(
    comparison: pd.DataFrame,
    first_label: str,
    second_label: str,
    language: str,
) -> None:
    """Показывает KPI городов в двух отдельных колонках."""
    st.subheader(ui('Сводные показатели', 'Summary indicators', language))

    first_column, second_column = st.columns(
        2,
        gap='large',
    )

    with first_column:
        show_city_kpis(
            comparison,
            first_label,
            'first',
            STEEL_BLUE,
            language,
        )

    with second_column:
        show_city_kpis(
            comparison,
            second_label,
            'second',
            SAGE_GREEN,
            language,
        )

    temperature = paired_metric_data(
        comparison,
        'average_temperature',
    )

    difference = (
        temperature['average_temperature_first']
        - temperature['average_temperature_second']
    ).mean()

    st.divider()

    difference_column, days_column = st.columns(2)

    with difference_column:
        st.metric(
            ui(
                'Разница средних температур',
                'Average temperature difference',
                language,
            ),
            (f'{difference:+.1f} °C' if pd.notna(difference) else '—'),
        )

        st.caption(
            ui(
                'Первый город относительно второго',
                'First city relative to second',
                language,
            )
        )

    with days_column:
        st.metric(
            ui(
                'Общих дней наблюдений',
                'Common observation days',
                language,
            ),
            len(comparison),
        )

    st.caption(
        ui(
            'Каждый показатель рассчитывается только по датам, '
            'для которых есть значения у обоих городов.',
            'Each metric uses dates with values for both cities.',
            language,
        )
    )


def get_aggregation_frequency(
    days: int,
) -> tuple[str | None, str]:
    """Выбирает детализацию графика по длине периода."""
    if days <= 31:
        return None, 'daily'

    if days <= 120:
        return 'W-MON', 'weekly'

    if days <= 730:
        return 'MS', 'monthly'

    return 'YS', 'yearly'


def prepare_metric_chart_data(
    comparison: pd.DataFrame,
    metric: str,
    first_label: str,
    second_label: str,
) -> tuple[pd.DataFrame, str]:
    """Подготавливает значения двух городов для сравнительного графика."""
    paired = paired_metric_data(
        comparison,
        metric,
    )

    if paired.empty:
        return pd.DataFrame(), 'daily'

    days = (
        comparison['weather_date'].max() - comparison['weather_date'].min()
    ).days + 1

    frequency, detail = get_aggregation_frequency(days)

    if frequency is not None:
        aggregation = METRICS[metric]['aggregation']

        paired = (
            paired.set_index('weather_date')
            .resample(frequency)
            .agg(aggregation)
            .dropna(how='all')
            .reset_index()
        )

    first_column = f'{metric}_first'
    second_column = f'{metric}_second'

    chart_data = paired.melt(
        id_vars=['weather_date'],
        value_vars=[first_column, second_column],
        var_name='city',
        value_name='value',
    ).dropna(subset=['value'])

    chart_data['city'] = chart_data['city'].map(
        {
            first_column: first_label,
            second_column: second_label,
        }
    )

    formats = {
        'daily': '%d.%m.%Y',
        'weekly': '%d.%m.%Y',
        'monthly': '%m.%Y',
        'yearly': '%Y',
    }

    chart_data['date_label'] = chart_data['weather_date'].dt.strftime(formats[detail])

    return chart_data, detail


def show_metric_comparison(
    comparison: pd.DataFrame,
    metric: str,
    first_label: str,
    second_label: str,
    language: str,
) -> None:
    """Строит график сравнения выбранного погодного показателя."""
    settings = METRICS[metric]

    chart_data, detail = prepare_metric_chart_data(
        comparison,
        metric,
        first_label,
        second_label,
    )

    if chart_data.empty:
        st.info(
            ui(
                'Нет общих данных для выбранного показателя.',
                'No shared data for the selected indicator.',
                language,
            )
        )
        return

    detail_labels = {
        'daily': ui('По дням', 'Daily', language),
        'weekly': ui('По неделям', 'Weekly', language),
        'monthly': ui('По месяцам', 'Monthly', language),
        'yearly': ui('По годам', 'Yearly', language),
    }

    st.caption(detail_labels[detail])

    label = settings[language]
    unit = settings['unit']

    color = alt.Color(
        'city:N',
        scale=alt.Scale(
            domain=[first_label, second_label],
            range=list(CITY_COLORS),
        ),
        legend=alt.Legend(
            title=None,
            orient='top',
            symbolSize=180,
            labelFontSize=13,
        ),
    )

    tooltip = [
        alt.Tooltip(
            'date_label:N',
            title=ui('Дата / период', 'Date / period', language),
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
    ]

    if settings['chart_type'] == 'bar':
        # Для коротких периодов показываем дни,
        # для длинных — предварительно агрегированные интервалы.
        period_count = chart_data['date_label'].nunique()

        chart = (
            alt.Chart(chart_data)
            .mark_bar()
            .encode(
                x=alt.X(
                    'date_label:N',
                    title=ui('Период', 'Period', language),
                    sort=alt.SortField(
                        field='weather_date',
                        order='ascending',
                    ),
                    axis=alt.Axis(
                        labelAngle=0 if period_count <= 12 else -45,
                        labelOverlap=True,
                    ),
                ),
                xOffset=alt.XOffset(
                    'city:N',
                    sort=[first_label, second_label],
                ),
                y=alt.Y(
                    'value:Q',
                    title=f'{label}, {unit}',
                    scale=alt.Scale(zero=True),
                ),
                color=color,
                tooltip=tooltip,
            )
        )

    else:
        ticks = get_date_ticks(
            chart_data,
            'weather_date',
        )
        date_format = get_date_format(
            chart_data,
            'weather_date',
        )

        chart = (
            alt.Chart(chart_data)
            .mark_line(
                point=detail != 'daily',
                strokeWidth=2.5,
            )
            .encode(
                x=alt.X(
                    'weather_date:T',
                    title=ui('Дата', 'Date', language),
                    axis=alt.Axis(
                        values=ticks,
                        format=date_format,
                        labelAngle=0,
                    ),
                ),
                y=alt.Y(
                    'value:Q',
                    title=f'{label}, {unit}',
                    scale=alt.Scale(zero=False),
                ),
                color=color,
                strokeDash=alt.StrokeDash(
                    'city:N',
                    scale=alt.Scale(
                        domain=[first_label, second_label],
                        range=[[1, 0], [7, 5]],
                    ),
                    legend=None,
                ),
                tooltip=tooltip,
            )
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
    """Отображает страницу сравнения двух городов."""
    with comparison_tab:
        st.header(translate('compare', language))

        if len(city_ids) < 2:
            st.info(translate('need_cities', language))
            return

        # Сохраняем выбранные идентификаторы при смене языка.
        if st.session_state.get('current_first_city_id') not in city_ids:
            st.session_state.current_first_city_id = city_ids[0]

        if st.session_state.get('current_second_city_id') not in city_ids:
            st.session_state.current_second_city_id = city_ids[1]

        st.sidebar.divider()

        first_city_id = st.sidebar.selectbox(
            translate('first_city', language),
            options=city_ids,
            index=city_ids.index(st.session_state.current_first_city_id),
            format_func=lambda city_id: city_name(
                city_records[city_id]['name'],
                city_records[city_id]['country'],
                language,
            ),
            key=f'compare_first_city_{language}',
        )

        second_city_id = st.sidebar.selectbox(
            translate('second_city', language),
            options=city_ids,
            index=city_ids.index(st.session_state.current_second_city_id),
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
            st.error(f'{translate("db_error", language)}: {error}')
            return

        if first_history.empty or second_history.empty:
            st.info(translate('need_history', language))
            return

        comparison = prepare_comparison(
            first_history,
            second_history,
        )

        if comparison.empty:
            st.info(
                ui(
                    'У выбранных городов нет общих дат наблюдений.',
                    'The selected cities have no common observation dates.',
                    language,
                )
            )
            return

        comparison = select_comparison_period(
            comparison,
            language,
        )

        if comparison.empty:
            st.info(
                ui(
                    'За выбранный период нет общих наблюдений.',
                    'No common observations in the selected period.',
                    language,
                )
            )
            return

        st.caption(
            f'{comparison["weather_date"].min():%d.%m.%Y} — '
            f'{comparison["weather_date"].max():%d.%m.%Y}'
        )

        show_comparison_kpis(
            comparison,
            first_label,
            second_label,
            language,
        )

        st.divider()

        st.subheader(
            ui(
                'Сравнение погодных показателей',
                'Weather indicator comparison',
                language,
            )
        )

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

        with st.expander(
            ui(
                'Данные сравнения',
                'Comparison data',
                language,
            )
        ):
            st.dataframe(
                comparison,
                hide_index=True,
                width='stretch',
            )

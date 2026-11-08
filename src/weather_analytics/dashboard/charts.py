"""Подготовка данных и построение графиков погодного дашборда."""

import altair as alt
import pandas as pd
import streamlit as st

from weather_analytics.dashboard.constants import (
    EXTRA_COLORS,
    EXTRA_UNITS,
    SAGE_GREEN,
    STEEL_BLUE,
)
from weather_analytics.dashboard.weather_ui import pressure_to_mmhg, ui
from weather_analytics.localization import translate


def prepare_local_time(
    dataframe: pd.DataFrame,
    time_column: str,
    timezone: str,
) -> pd.DataFrame:
    """Переводит время UTC в местное время выбранного города."""
    result = dataframe.copy()

    result['local_time'] = (
        pd.to_datetime(result[time_column], utc=True)
        .dt.tz_convert(timezone)
        .dt.tz_localize(None)
    )

    result['date_label'] = result['local_time'].dt.strftime('%d.%m.%Y %H:%M')

    return result


def get_date_ticks(
    dataframe: pd.DataFrame,
    date_column: str,
) -> list:
    """Возвращает по одной отметке на каждый календарный день."""
    if dataframe.empty or date_column not in dataframe:
        return []

    dates = pd.to_datetime(
        dataframe[date_column],
        errors='coerce',
    ).dropna()

    if dates.empty:
        return []

    # Нормализация времени убирает повторяющиеся отметки внутри суток.
    return dates.dt.normalize().drop_duplicates().sort_values().tolist()


def date_axis(
    ticks: list,
    language: str,
    hourly: bool = False,
) -> alt.X:
    """Создаёт единую ось дат без автоматических почасовых подписей."""
    return alt.X(
        'local_time:T' if hourly else 'weather_date:T',
        title=translate(
            'datetime' if hourly else 'date',
            language,
        ),
        axis=alt.Axis(
            values=ticks,
            format='%d.%m',
            labelAngle=0,
            grid=True,
        ),
    )


def prepare_daily_chart(
    dataframe: pd.DataFrame,
    date_column: str,
    columns: list[str],
    labels: list[str],
    extra_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Преобразует ежедневные показатели в длинный формат."""
    extra_columns = extra_columns or []

    result = dataframe[[date_column, *columns, *extra_columns]].copy()

    result['date_label'] = pd.to_datetime(result[date_column]).dt.strftime('%d.%m.%Y')

    result = result.melt(
        id_vars=[date_column, 'date_label', *extra_columns],
        value_vars=columns,
        var_name='indicator',
        value_name='value',
    )

    result['indicator'] = result['indicator'].map(
        dict(zip(columns, labels, strict=True))
    )

    return result


def show_daily_chart(
    dataframe: pd.DataFrame,
    date_column: str,
    columns: list[str],
    labels: list[str],
    colors: list[str],
    y_title: str,
    language: str,
    chart_type: str = 'line',
    extra_tooltips: list[alt.Tooltip] | None = None,
) -> None:
    """Строит ежедневный график с корректным масштабом и датами."""
    if dataframe.empty:
        return

    chart_data = prepare_daily_chart(
        dataframe,
        date_column,
        columns,
        labels,
    )

    chart_data = chart_data.dropna(subset=['value'])

    if chart_data.empty:
        st.info(
            ui(
                'Нет данных для графика.',
                'No data available for this chart.',
                language,
            )
        )
        return

    ticks = get_date_ticks(dataframe, date_column)

    # Начинаем ось Y с нуля для сопоставимости масштабов графиков.
    y_scale = alt.Scale(zero=True)

    tooltip = [
        alt.Tooltip(
            'date_label:N',
            title=translate('date', language),
        ),
        alt.Tooltip(
            'indicator:N',
            title=translate('indicator', language),
        ),
        alt.Tooltip(
            'value:Q',
            title=y_title,
            format='.1f',
        ),
    ]

    if extra_tooltips:
        tooltip.extend(extra_tooltips)

    base = alt.Chart(chart_data).encode(
        x=alt.X(
            f'{date_column}:T',
            title=translate('date', language),
            axis=alt.Axis(
                values=ticks,
                format='%d.%m',
                labelAngle=0,
                grid=True,
            ),
        ),
        y=alt.Y(
            'value:Q',
            title=y_title,
            scale=y_scale,
        ),
        color=alt.Color(
            'indicator:N',
            scale=alt.Scale(
                domain=labels,
                range=colors,
            ),
            legend=(alt.Legend(title=None) if len(labels) > 1 else None),
        ),
        tooltip=tooltip,
    )

    if chart_type == 'bar':
        chart = base.mark_bar(size=22)
    else:
        chart = base.mark_line(
            point=True,
            strokeWidth=2.5,
        )

    st.altair_chart(
        chart.properties(height=340),
        width='stretch',
    )


def show_hourly_chart(
    dataframe: pd.DataFrame,
    column: str,
    title: str,
    color: str,
    unit: str,
    language: str,
) -> None:
    """Строит почасовой график с одной подписью на каждый день."""
    st.subheader(title)

    if dataframe.empty or column not in dataframe:
        st.info(
            ui(
                'Нет почасовых данных.',
                'No hourly data available.',
                language,
            )
        )
        return

    plot_data = dataframe.dropna(subset=['local_time', column]).copy()

    if plot_data.empty:
        return

    ticks = get_date_ticks(plot_data, 'local_time')

    chart = (
        alt.Chart(plot_data)
        .mark_line(
            color=color,
            strokeWidth=2.2,
        )
        .encode(
            x=alt.X(
                'local_time:T',
                title=translate('datetime', language),
                axis=alt.Axis(
                    values=ticks,
                    format='%d.%m',
                    labelAngle=0,
                    grid=True,
                ),
            ),
            y=alt.Y(
                f'{column}:Q',
                title=f'{title}, {unit}',
                scale=alt.Scale(zero=False),
            ),
            tooltip=[
                alt.Tooltip(
                    'date_label:N',
                    title=translate('datetime', language),
                ),
                alt.Tooltip(
                    f'{column}:Q',
                    title=title,
                    format='.1f',
                ),
            ],
        )
        .properties(height=320)
        .interactive()
    )

    st.altair_chart(chart, width='stretch')


def show_comparison_chart(
    first_data: pd.DataFrame,
    second_data: pd.DataFrame,
    first_label: str,
    second_label: str,
    language: str,
) -> None:
    """Сравнивает среднесуточную температуру двух городов."""
    first = first_data[['weather_date', 'average_temperature']].copy()

    second = second_data[['weather_date', 'average_temperature']].copy()

    comparison = first.merge(
        second,
        on='weather_date',
        how='inner',
        suffixes=('_first', '_second'),
    ).sort_values('weather_date')

    if comparison.empty:
        st.info(translate('no_common', language))
        return

    comparison['date_label'] = comparison['weather_date'].dt.strftime('%d.%m.%Y')

    chart_data = comparison.melt(
        id_vars=['weather_date', 'date_label'],
        value_vars=[
            'average_temperature_first',
            'average_temperature_second',
        ],
        var_name='city',
        value_name='temperature',
    )

    chart_data['city'] = chart_data['city'].map(
        {
            'average_temperature_first': first_label,
            'average_temperature_second': second_label,
        }
    )

    ticks = get_date_ticks(comparison, 'weather_date')

    chart = (
        alt.Chart(chart_data)
        .mark_line(
            point=True,
            strokeWidth=2.5,
        )
        .encode(
            x=alt.X(
                'weather_date:T',
                title=translate('date', language),
                axis=alt.Axis(
                    values=ticks,
                    format='%d.%m',
                    labelAngle=0,
                ),
            ),
            y=alt.Y(
                'temperature:Q',
                title=translate('compare_temp', language),
                scale=alt.Scale(zero=True),
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
                    title=translate('date', language),
                ),
                alt.Tooltip(
                    'city:N',
                    title=translate('city', language),
                ),
                alt.Tooltip(
                    'temperature:Q',
                    title=translate('temp_axis', language),
                    format='.1f',
                ),
            ],
        )
        .properties(height=380)
    )

    st.altair_chart(chart, width='stretch')

    st.caption(f'{translate("common_days", language)}: {len(comparison)}')


# ---------------------------------------------------------
# Дополнительные показатели
# ---------------------------------------------------------


def show_extra_charts(
    dataframe: pd.DataFrame,
    time_column: str,
    columns: tuple[str, ...],
    language: str,
    timezone: str,
    daily: bool = False,
) -> None:
    """Строит дополнительные графики с компактной осью дат."""
    if dataframe.empty:
        st.info(translate('no_extra', language))
        return

    plot_data = dataframe.copy()

    if not daily:
        plot_data = prepare_local_time(
            plot_data,
            time_column,
            timezone,
        )
        x_column = 'local_time'
    else:
        x_column = time_column

    ticks = get_date_ticks(plot_data, x_column)
    shown = 0

    for index, column in enumerate(columns):
        if column not in plot_data:
            continue

        values = plot_data[[x_column, column]].dropna().copy()

        if values.empty:
            continue

        shown += 1

        # Приводим дополнительные показатели к единицам,
        # понятным пользователю.
        if column == 'pressure_msl':
            values[column] = pressure_to_mmhg(values[column])

        if column in ('sunshine_duration', 'daylight_duration'):
            values[column] = values[column] / 3600

        label = translate(column, language)
        unit = EXTRA_UNITS[column]

        if column == 'pressure_msl':
            unit = ui('мм рт. ст.', 'mmHg', language)

        title = f'{label}, {unit}' if unit else label

        st.subheader(label)

        # Полная дата и время доступны при наведении.
        values['time_label'] = pd.to_datetime(values[x_column]).dt.strftime(
            '%d.%m.%Y' if daily else '%d.%m.%Y %H:%M'
        )

        chart = (
            alt.Chart(values)
            .mark_line(
                point=daily,
                strokeWidth=2.2,
                color=EXTRA_COLORS[index % len(EXTRA_COLORS)],
            )
            .encode(
                x=alt.X(
                    f'{x_column}:T',
                    title=translate(
                        'date' if daily else 'datetime',
                        language,
                    ),
                    axis=alt.Axis(
                        values=ticks,
                        format='%d.%m',
                        labelAngle=0,
                        grid=True,
                    ),
                ),
                y=alt.Y(
                    f'{column}:Q',
                    title=title,
                    scale=alt.Scale(zero=False),
                ),
                tooltip=[
                    alt.Tooltip(
                        'time_label:N',
                        title=translate(
                            'date' if daily else 'datetime',
                            language,
                        ),
                    ),
                    alt.Tooltip(
                        f'{column}:Q',
                        title=title,
                        format='.2f',
                    ),
                ],
            )
            .properties(height=260)
            .interactive()
        )

        st.altair_chart(chart, width='stretch')

    if not shown:
        st.info(translate('no_extra', language))

"""Интерфейс вкладки семидневного прогноза погоды."""

from html import escape

import altair as alt
import pandas as pd
import psycopg
import streamlit as st

from weather_analytics.dashboard.charts import get_date_ticks
from weather_analytics.dashboard.constants import (
    CLOUD_BLUE,
    LIGHT_CORAL,
    METRIC_COLORS,
    MUTED_PURPLE,
    SAGE_GREEN,
    STEEL_BLUE,
)
from weather_analytics.dashboard.data import (
    load_forecast_hourly_details,
    load_forecast_precipitation_events,
)
from weather_analytics.dashboard.forecast_data import load_forecast_overview
from weather_analytics.dashboard.weather_ui import (
    pressure_to_mmhg,
    show_sun_and_moon,
    show_wind_compass,
    ui,
)
from weather_analytics.localization import translate


def prepare_hourly_time(
    dataframe: pd.DataFrame,
    timezone_name: str,
) -> pd.DataFrame:
    """Подготавливает местное время для почасовых графиков."""
    result = dataframe.copy()

    result['local_time'] = (
        pd.to_datetime(result['forecast_time'], utc=True)
        .dt.tz_convert(timezone_name)
        .dt.tz_localize(None)
    )

    result['time_label'] = result['local_time'].dt.strftime('%d.%m.%Y %H:%M')

    return result


def show_hourly_lines(
    dataframe: pd.DataFrame,
    columns: tuple[str, ...],
    labels: tuple[str, ...],
    colors: tuple[str, ...],
    unit: str,
    language: str,
    height: int = 300,
    zero: bool = True,
    dashed_second: bool = False,
) -> None:
    """Строит почасовые линии с одной отметкой на календарный день."""
    available = [
        (column, label, color)
        for column, label, color in zip(columns, labels, colors, strict=True)
        if column in dataframe and dataframe[column].notna().any()
    ]

    if not available:
        st.info(
            ui(
                'Нет данных для графика.',
                'No data available for this chart.',
                language,
            )
        )
        return

    selected_columns = [item[0] for item in available]
    selected_labels = [item[1] for item in available]
    selected_colors = [
        METRIC_COLORS.get(column, color) for column, _, color in available
    ]

    chart_data = (
        dataframe[['local_time', 'time_label', *selected_columns]]
        .melt(
            id_vars=['local_time', 'time_label'],
            value_vars=selected_columns,
            var_name='indicator',
            value_name='value',
        )
        .dropna(subset=['value'])
    )

    chart_data['indicator'] = chart_data['indicator'].map(
        dict(zip(selected_columns, selected_labels, strict=True))
    )

    if dashed_second:
        chart_data['line_style'] = chart_data['indicator'].map(
            {
                label: ('dashed' if column == 'wind_gusts' else 'solid')
                for column, label in zip(selected_columns, selected_labels, strict=True)
            }
        )

    ticks = get_date_ticks(dataframe, 'local_time')

    chart = (
        alt.Chart(chart_data)
        .mark_line(strokeWidth=2.2)
        .encode(
            x=alt.X(
                'local_time:T',
                title=ui('Дата и время', 'Date and time', language),
                axis=alt.Axis(
                    values=ticks,
                    format='%d.%m',
                    labelAngle=0,
                    grid=True,
                ),
            ),
            y=alt.Y(
                'value:Q',
                title=unit,
                scale=alt.Scale(zero=zero),
            ),
            color=alt.Color(
                'indicator:N',
                scale=alt.Scale(
                    domain=selected_labels,
                    range=selected_colors,
                ),
                legend=(
                    alt.Legend(title=None)
                    if len(selected_labels) > 1 and not dashed_second
                    else None
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    'time_label:N',
                    title=ui('Время', 'Time', language),
                ),
                alt.Tooltip(
                    'indicator:N',
                    title=ui('Показатель', 'Indicator', language),
                ),
                alt.Tooltip(
                    'value:Q',
                    title=unit,
                    format='.1f',
                ),
            ],
        )
        .properties(height=height)
    )

    if dashed_second:
        chart = chart.encode(
            strokeDash=alt.StrokeDash(
                'line_style:N',
                scale=alt.Scale(
                    domain=['solid', 'dashed'],
                    range=[[], [8, 5]],
                ),
                legend=None,
            )
        )

    if dashed_second:
        legend_items = []

        for column, label, color in zip(
            selected_columns,
            selected_labels,
            selected_colors,
            strict=True,
        ):
            line_style = 'dashed' if column == 'wind_gusts' else 'solid'

            legend_items.append(
                '<span style="display:inline-flex;align-items:center;gap:8px;">'
                f'<span style="width:36px;border-top:3px {line_style} {color};"></span>'
                f'{escape(label)}</span>'
            )

        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:22px;">'
            + ''.join(legend_items)
            + '</div>',
            unsafe_allow_html=True,
        )

    st.altair_chart(chart, width='stretch')


def show_temperature(
    daily: pd.DataFrame,
    hourly: pd.DataFrame,
    language: str,
) -> None:
    """Показывает дневную и почасовую температуру."""
    st.subheader(ui('Температура', 'Temperature', language))

    daily_columns = [
        ('temperature_min', ui('Минимум', 'Minimum', language), LIGHT_CORAL),
        ('temperature_mean', ui('Средняя', 'Average', language), STEEL_BLUE),
        ('temperature_max', ui('Максимум', 'Maximum', language), SAGE_GREEN),
    ]

    available = [
        item
        for item in daily_columns
        if item[0] in daily and daily[item[0]].notna().any()
    ]

    if available:
        columns = [item[0] for item in available]
        labels = [item[1] for item in available]
        colors = [item[2] for item in available]

        chart_data = (
            daily[['forecast_date', *columns]]
            .melt(
                id_vars='forecast_date',
                value_vars=columns,
                var_name='indicator',
                value_name='temperature',
            )
            .dropna(subset=['temperature'])
        )

        chart_data['indicator'] = chart_data['indicator'].map(
            dict(zip(columns, labels, strict=True))
        )

        ticks = get_date_ticks(daily, 'forecast_date')

        chart = (
            alt.Chart(chart_data)
            .mark_line(point=True, strokeWidth=2.5)
            .encode(
                x=alt.X(
                    'forecast_date:T',
                    title=ui('Дата', 'Date', language),
                    axis=alt.Axis(
                        values=ticks,
                        format='%d.%m',
                        labelAngle=0,
                        grid=True,
                    ),
                ),
                y=alt.Y(
                    'temperature:Q',
                    title='°C',
                    scale=alt.Scale(zero=True),
                ),
                color=alt.Color(
                    'indicator:N',
                    scale=alt.Scale(
                        domain=labels,
                        range=colors,
                    ),
                    legend=alt.Legend(title=None),
                ),
                tooltip=[
                    alt.Tooltip(
                        'forecast_date:T',
                        title=ui('Дата', 'Date', language),
                        format='%d.%m.%Y',
                    ),
                    alt.Tooltip(
                        'indicator:N',
                        title=ui('Показатель', 'Indicator', language),
                    ),
                    alt.Tooltip(
                        'temperature:Q',
                        title='°C',
                        format='.1f',
                    ),
                ],
            )
            .properties(height=320)
        )

        st.altair_chart(chart, width='stretch')

    st.markdown(f'**{ui("Температура по часам", "Hourly temperature", language)}**')

    show_hourly_lines(
        hourly,
        ('temperature', 'apparent_temperature'),
        (
            ui('Температура', 'Temperature', language),
            ui('Ощущается как', 'Feels like', language),
        ),
        (STEEL_BLUE, SAGE_GREEN),
        '°C',
        language,
    )


def show_precipitation(
    daily: pd.DataFrame,
    hourly: pd.DataFrame,
    language: str,
) -> None:
    """Показывает количество осадков и вероятность их выпадения."""
    st.subheader(ui('Осадки', 'Precipitation', language))

    precipitation = pd.to_numeric(
        daily['precipitation'],
        errors='coerce',
    )

    if precipitation.notna().any() and precipitation.gt(0).any():
        chart_data = daily[['forecast_date', 'precipitation']].copy()
        ticks = get_date_ticks(daily, 'forecast_date')

        chart = (
            alt.Chart(chart_data)
            .mark_bar(color=STEEL_BLUE, size=24)
            .encode(
                x=alt.X(
                    'forecast_date:T',
                    title=ui('Дата', 'Date', language),
                    axis=alt.Axis(
                        values=ticks,
                        format='%d.%m',
                        labelAngle=0,
                    ),
                ),
                y=alt.Y(
                    'precipitation:Q',
                    title=ui('Осадки, мм', 'Precipitation, mm', language),
                    scale=alt.Scale(zero=True),
                ),
                tooltip=[
                    alt.Tooltip(
                        'forecast_date:T',
                        title=ui('Дата', 'Date', language),
                        format='%d.%m.%Y',
                    ),
                    alt.Tooltip(
                        'precipitation:Q',
                        title=ui('Осадки, мм', 'Precipitation, mm', language),
                        format='.1f',
                    ),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(chart, width='stretch')
    elif precipitation.notna().any():
        st.info(
            ui(
                'По дневному прогнозу осадки не ожидаются.',
                'No precipitation is expected in the daily forecast.',
                language,
            )
        )
    else:
        st.info(
            ui(
                'Нет данных о дневных осадках.',
                'Daily precipitation data is unavailable.',
                language,
            )
        )

    if (
        'precipitation_probability' in hourly
        and hourly['precipitation_probability'].fillna(0).gt(0).any()
    ):
        st.markdown(
            f'**{
                ui(
                    "Вероятность осадков по часам",
                    "Hourly precipitation probability",
                    language,
                )
            }**'
        )

        show_hourly_lines(
            hourly,
            ('precipitation_probability',),
            (ui('Вероятность осадков', 'Precipitation probability', language),),
            (STEEL_BLUE,),
            '%',
            language,
        )


def describe_precipitation(row: pd.Series, language: str) -> str:
    """Определяет вид осадков по компонентам почасового прогноза."""
    rain = float(row['rain']) if pd.notna(row['rain']) else 0.0
    showers = float(row['showers']) if pd.notna(row['showers']) else 0.0
    snowfall = float(row['snowfall']) if pd.notna(row['snowfall']) else 0.0

    if snowfall > 0 and (rain > 0 or showers > 0):
        return ui('Смешанные осадки', 'Mixed precipitation', language)

    if snowfall > 0:
        return ui('Снег', 'Snow', language)

    if showers > 0:
        return ui('Ливневый дождь', 'Rain showers', language)

    if rain > 0:
        return ui('Дождь', 'Rain', language)

    return ui(
        'Осадки, тип не определён',
        'Precipitation, type unknown',
        language,
    )


def show_precipitation_events(
    city_id: int,
    fetched_at: pd.Timestamp,
    timezone_name: str,
    language: str,
) -> None:
    """Показывает только дни и часы с ожидаемыми осадками."""
    st.subheader(
        ui(
            'Когда ожидаются осадки',
            'When precipitation is expected',
            language,
        )
    )

    try:
        events = load_forecast_precipitation_events(
            city_id,
            fetched_at,
        )
    except psycopg.Error as error:
        st.error(
            ui(
                f'Не удалось загрузить данные об осадках: {error}',
                f'Failed to load precipitation data: {error}',
                language,
            )
        )
        return

    if events.empty:
        st.info(
            ui(
                'В ближайшие 7 дней осадки не ожидаются.',
                'No precipitation is expected over the next 7 days.',
                language,
            )
        )
        return

    events['local_time'] = events['forecast_time'].dt.tz_convert(timezone_name)
    events['date'] = events['local_time'].dt.date
    events['time'] = events['local_time'].dt.strftime('%H:%M')

    events['description'] = events.apply(
        lambda row: describe_precipitation(row, language),
        axis=1,
    )

    st.caption(
        ui(
            'Показаны только часы с ненулевым количеством осадков. '
            'Тип определяется по дождю, ливням и снегу в почасовом прогнозе.',
            'Only hours with nonzero precipitation are shown. '
            'Type is determined from hourly rain, showers and snowfall.',
            language,
        )
    )

    for day, group in events.groupby('date', sort=True):
        with st.expander(
            day.strftime('%d.%m.%Y'),
            expanded=True,
        ):
            display = group[['time', 'description', 'precipitation']].copy()

            display.columns = [
                ui('Время', 'Time', language),
                ui('Тип осадков', 'Precipitation type', language),
                ui('Осадки, мм', 'Precipitation, mm', language),
            ]

            st.dataframe(
                display,
                hide_index=True,
                width='stretch',
            )


def show_wind(
    daily: pd.DataFrame,
    hourly: pd.DataFrame,
    language: str,
) -> None:
    """Показывает скорость ветра, порывы и общий компас."""
    st.subheader(ui('Ветер', 'Wind', language))

    show_hourly_lines(
        hourly,
        ('wind_speed', 'wind_gusts'),
        (
            ui('Скорость ветра', 'Wind speed', language),
            ui('Порывы ветра', 'Wind gusts', language),
        ),
        (METRIC_COLORS['wind_speed'], METRIC_COLORS['wind_gusts']),
        ui('км/ч', 'km/h', language),
        language,
        dashed_second=True,
    )

    if (
        'wind_direction_dominant' in daily
        and daily['wind_direction_dominant'].notna().any()
    ):
        show_wind_compass(
            daily,
            language,
            date_column='forecast_date',
            key='forecast_wind_compass_day',
        )


def show_uv(
    daily: pd.DataFrame,
    hourly: pd.DataFrame,
    language: str,
) -> None:
    """Показывает ультрафиолетовый индекс и его максимальное значение."""
    st.subheader(ui('УФ-индекс', 'UV index', language))

    if 'uv_index' in hourly and hourly['uv_index'].notna().any():
        show_hourly_lines(
            hourly,
            ('uv_index',),
            (ui('УФ-индекс', 'UV index', language),),
            (MUTED_PURPLE,),
            ui('Индекс', 'Index', language),
            language,
        )

    if 'uv_index_max' in daily and daily['uv_index_max'].notna().any():
        maximum = float(daily['uv_index_max'].max())

        if maximum < 3:
            category = ui('Низкий', 'Low', language)
        elif maximum < 6:
            category = ui('Умеренный', 'Moderate', language)
        elif maximum < 8:
            category = ui('Высокий', 'High', language)
        elif maximum < 11:
            category = ui('Очень высокий', 'Very high', language)
        else:
            category = ui('Экстремальный', 'Extreme', language)

        st.metric(
            ui('Максимальный УФ-индекс', 'Maximum UV index', language),
            f'{maximum:.1f}',
        )
        st.caption(category)


def show_humidity(
    hourly: pd.DataFrame,
    language: str,
) -> None:
    """Показывает влажность воздуха и точку росы."""
    st.subheader(
        ui(
            'Влажность и точка росы',
            'Humidity and dew point',
            language,
        )
    )

    st.markdown(f'**{ui("Относительная влажность", "Relative humidity", language)}**')

    show_hourly_lines(
        hourly,
        ('humidity',),
        (ui('Относительная влажность', 'Relative humidity', language),),
        (STEEL_BLUE,),
        '%',
        language,
    )

    if 'dew_point' in hourly and hourly['dew_point'].notna().any():
        st.markdown(f'**{ui("Точка росы", "Dew point", language)}**')

        show_hourly_lines(
            hourly,
            ('dew_point',),
            (ui('Точка росы', 'Dew point', language),),
            (SAGE_GREEN,),
            '°C',
            language,
        )


def show_additional(
    hourly: pd.DataFrame,
    language: str,
) -> None:
    """Показывает дополнительные графики с отдельными названиями."""
    st.subheader(
        ui(
            'Дополнительные показатели',
            'Additional metrics',
            language,
        )
    )

    if 'cloud_cover' in hourly and hourly['cloud_cover'].notna().any():
        st.markdown(f'**{ui("Облачность", "Cloud cover", language)}**')

        show_hourly_lines(
            hourly,
            ('cloud_cover',),
            (ui('Облачность', 'Cloud cover', language),),
            (CLOUD_BLUE,),
            '%',
            language,
        )

    if 'pressure_msl' in hourly and hourly['pressure_msl'].notna().any():
        pressure = hourly.copy()
        pressure['pressure_msl'] = pressure_to_mmhg(pressure['pressure_msl'])

        st.markdown(
            f'**{ui("Атмосферное давление", "Atmospheric pressure", language)}**'
        )

        show_hourly_lines(
            pressure,
            ('pressure_msl',),
            (ui('Атмосферное давление', 'Atmospheric pressure', language),),
            (METRIC_COLORS['pressure_msl'],),
            ui('мм рт. ст.', 'mmHg', language),
            language,
            zero=False,
        )

    if 'visibility' in hourly and hourly['visibility'].notna().any():
        visibility = hourly.copy()
        visibility['visibility'] = (
            pd.to_numeric(
                visibility['visibility'],
                errors='coerce',
            )
            / 1000
        )

        st.markdown(f'**{ui("Видимость", "Visibility", language)}**')

        show_hourly_lines(
            visibility,
            ('visibility',),
            (ui('Видимость', 'Visibility', language),),
            (METRIC_COLORS['visibility'],),
            ui('км', 'km', language),
            language,
        )


def render_forecast_tab(
    selected_city_id: int,
    city_timezone: str,
    language: str,
) -> None:
    """Отображает семидневный прогноз выбранного города."""
    try:
        daily = load_forecast_overview(selected_city_id)

        if daily.empty:
            st.info(translate('no_forecast', language))
            return

        fetched_at = pd.Timestamp(daily['fetched_at'].iloc[0])

        hourly = load_forecast_hourly_details(
            selected_city_id,
            fetched_at,
        )

    except psycopg.Error as error:
        st.error(
            ui(
                f'Ошибка загрузки прогноза: {error}',
                f'Forecast loading error: {error}',
                language,
            )
        )
        return

    st.caption(
        f'{ui("Обновление прогноза", "Forecast updated", language)}: '
        f'{fetched_at.tz_convert(city_timezone).strftime("%d.%m.%Y %H:%M")}'
    )

    if hourly.empty:
        st.info(
            ui(
                'Почасовой прогноз пока недоступен.',
                'Hourly forecast is not available yet.',
                language,
            )
        )
        hourly = pd.DataFrame(columns=['local_time', 'time_label'])
    else:
        hourly = prepare_hourly_time(hourly, city_timezone)

    show_temperature(daily, hourly, language)

    st.divider()
    show_precipitation(daily, hourly, language)
    show_precipitation_events(
        selected_city_id,
        fetched_at,
        city_timezone,
        language,
    )

    st.divider()
    show_wind(daily, hourly, language)

    st.divider()
    show_uv(daily, hourly, language)

    st.divider()
    show_humidity(hourly, language)

    st.divider()
    show_additional(hourly, language)

    st.divider()
    show_sun_and_moon(
        daily,
        city_timezone,
        language,
        date_column='forecast_date',
        key='forecast_sun_moon_day',
    )

    with st.expander(
        ui(
            'Исходные данные прогноза',
            'Forecast source data',
            language,
        )
    ):
        st.markdown(f'**{ui("По дням", "Daily", language)}**')
        st.dataframe(daily, hide_index=True, width='stretch')

        st.markdown(f'**{ui("По часам", "Hourly", language)}**')
        st.dataframe(hourly, hide_index=True, width='stretch')

# """Форматирование погодных данных для двуязычного бота Stormy.

# Преобразует текущие, суточные и почасовые данные в сообщения
# на русском и английском языках. Использует готовые расчётные
# функции и справочники локализации.

# Не выполняет API-запросы и не управляет Telegram-диалогами.
# """

# from datetime import date
# from html import escape

# from weather_analytics.bot.messages import (
#     LABELS,
#     MESSAGES,
#     MONTHS_EN,
#     MONTHS_RU,
#     WEEKDAYS_EN,
#     WEEKDAYS_RU,
# )
# from weather_analytics.bot.weather_calculations import (
#     compact_event_hours,
#     get_daily_value,
#     get_hourly_average,
#     get_hourly_events,
#     get_hourly_range,
#     get_hourly_values,
#     get_intensity_intervals,
#     get_period_temperature,
# )


# def format_number(
#     value,
#     digits: int = 1,
#     signed: bool = False,
# ) -> str:
#     """Форматирует число с точностью и необязательным знаком плюса."""
#     if value is None:
#         return '—'

#     number = round(float(value), digits)

#     if number == 0:
#         number = 0.0

#     text = (
#         f'{number:+.{digits}f}'
#         if signed
#         else f'{number:.{digits}f}'
#     )

#     if digits:
#         text = text.rstrip('0').rstrip('.')

#     return text


# def format_date(value: str, language: str) -> str:
#     """Преобразует ISO-дату в локализованный формат."""
#     day = date.fromisoformat(value[:10])

#     if language == 'ru':
#         weekday = WEEKDAYS_RU[day.weekday()]

#         return (
#             f'{weekday.capitalize()}, '
#             f'{day.day} {MONTHS_RU[day.month]} '
#             f'{day.year} года'
#         )

#     weekday = WEEKDAYS_EN[day.weekday()]

#     return (
#         f'{weekday}, '
#         f'{MONTHS_EN[day.month]} '
#         f'{day.day}, {day.year}'
#     )


# def format_value(
#     value,
#     unit: str = '',
#     digits: int = 1,
#     signed: bool = False,
# ) -> str:
#     """Добавляет единицу измерения к числовому значению."""
#     number = format_number(value, digits, signed)

#     return f'{number} {unit}'.strip()


# def format_current(
#     current: dict,
#     metrics: tuple,
#     language: str,
# ) -> list[str]:
#     """Формирует строки текущих погодных показателей."""
#     ru = language == 'ru'
#     lines = []

#     fields = {
#         'temperature': 'temperature_2m',
#         'feels_like': 'apparent_temperature',
#         'wind': 'wind_speed_10m',
#         'rain': 'rain',
#         'snow': 'snowfall',
#         'precipitation': 'precipitation',
#         'humidity': 'relative_humidity_2m',
#         'cloud': 'cloud_cover',
#         'pressure': 'pressure_msl',
#         'uv': 'uv_index',
#     }

#     for metric in metrics:
#         if metric not in LABELS:
#             continue

#         value = current.get(fields.get(metric))

#         if value is None:
#             continue

#         label = LABELS[metric][0 if ru else 1]
#         unit = LABELS[metric][2]

#         if not ru:
#             unit = {
#                 'км/ч': 'km/h',
#                 'мм': 'mm',
#                 'гПа': 'hPa',
#             }.get(unit, unit)

#         digits = (
#             1
#             if metric in (
#                 'temperature',
#                 'feels_like',
#                 'rain',
#                 'snow',
#                 'precipitation',
#                 'uv',
#             )
#             else 0
#         )

#         signed = metric in (
#             'temperature',
#             'feels_like',
#         )

#         lines.append(
#             f'{label}: '
#             f'{format_value(value, unit, digits, signed)}'
#         )

#     return lines


# def format_wind_direction(
#     value,
#     language: str,
# ) -> str | None:
#     """Преобразует направление ветра в сторону света и стрелку."""
#     if value is None:
#         return None

#     # Метеорологическое направление указывает,
#     # откуда дует ветер.
#     degrees = float(value) % 360
#     sector = int((degrees + 22.5) // 45) % 8

#     names_ru = (
#         'С (северный)',
#         'СВ (северо-восточный)',
#         'В (восточный)',
#         'ЮВ (юго-восточный)',
#         'Ю (южный)',
#         'ЮЗ (юго-западный)',
#         'З (западный)',
#         'СЗ (северо-западный)',
#     )

#     names_en = (
#         'N', 'NE', 'E', 'SE',
#         'S', 'SW', 'W', 'NW',
#     )

#     # Стрелка показывает направление движения ветра,
#     # противоположное метеорологическому направлению.
#     arrows = (
#         '↓', '↙', '←', '↖',
#         '↑', '↗', '→', '↘',
#     )

#     name = (
#         names_ru[sector]
#         if language == 'ru'
#         else names_en[sector]
#     )

#     return f'{name} {arrows[sector]}'


# def format_daily(
#     daily: dict,
#     hourly: dict,
#     day: str,
#     index: int,
#     metrics: tuple,
#     language: str,
#     compact: bool = False,
# ) -> list[str]:
#     """Оформляет суточные показатели выбранных погодных метрик."""
#     ru = language == 'ru'
#     lines = []

#     def add(
#         label_ru: str,
#         label_en: str,
#         value,
#         unit: str = '',
#         digits: int = 1,
#         signed: bool = False,
#     ) -> None:
#         """Добавляет показатель, если его значение доступно."""
#         if value is None:
#             return

#         label = label_ru if ru else label_en

#         lines.append(
#             f'{label}: '
#             f'{format_value(value, unit, digits, signed)}'
#         )

#     if 'temperature' in metrics:
#         minimum = get_daily_value(
#             daily,
#             'temperature_2m_min',
#             index,
#         )

#         maximum = get_daily_value(
#             daily,
#             'temperature_2m_max',
#             index,
#         )

#         if minimum is not None or maximum is not None:
#             lines.append(
#                 '🌡️ Температура'
#                 if ru
#                 else '🌡️ Temperature'
#             )

#             add(
#                 '  Минимальная',
#                 '  Minimum',
#                 minimum,
#                 '°C',
#                 signed=True,
#             )

#             add(
#                 '  Максимальная',
#                 '  Maximum',
#                 maximum,
#                 '°C',
#                 signed=True,
#             )

#             # Для одного дня показываем среднюю температуру
#             # по четырём периодам местных суток.
#             if not compact:
#                 periods = (
#                     (0, 5, '  Ночью', '  Night'),
#                     (6, 11, '  Утром', '  Morning'),
#                     (12, 17, '  Днём', '  Afternoon'),
#                     (18, 23, '  Вечером', '  Evening'),
#                 )

#                 for (
#                     start_hour,
#                     end_hour,
#                     label_ru,
#                     label_en,
#                 ) in periods:
#                     value = get_period_temperature(
#                         hourly,
#                         day,
#                         start_hour,
#                         end_hour,
#                     )

#                     add(
#                         label_ru,
#                         label_en,
#                         value,
#                         '°C',
#                         signed=True,
#                     )

#     if 'feels_like' in metrics:
#         minimum, maximum = get_hourly_range(
#             hourly,
#             day,
#             'apparent_temperature',
#         )

#         if minimum is None:
#             minimum = get_daily_value(
#                 daily,
#                 'apparent_temperature_min',
#                 index,
#             )

#         if maximum is None:
#             maximum = get_daily_value(
#                 daily,
#                 'apparent_temperature_max',
#                 index,
#             )

#         if minimum is not None or maximum is not None:
#             lines.append(
#                 '🤗 Ощущается как'
#                 if ru
#                 else '🤗 Feels like'
#             )

#             add(
#                 '  Минимальная',
#                 '  Minimum',
#                 minimum,
#                 '°C',
#                 signed=True,
#             )

#             add(
#                 '  Максимальная',
#                 '  Maximum',
#                 maximum,
#                 '°C',
#                 signed=True,
#             )

#     if 'wind' in metrics:
#         speed = get_daily_value(
#             daily,
#             'wind_speed_10m_max',
#             index,
#         )

#         gusts = get_daily_value(
#             daily,
#             'wind_gusts_10m_max',
#             index,
#         )

#         direction = get_daily_value(
#             daily,
#             'wind_direction_10m_dominant',
#             index,
#         )

#         unit = 'км/ч' if ru else 'km/h'

#         if any(
#             value is not None
#             for value in (speed, gusts, direction)
#         ):
#             lines.append(
#                 '🌬️ Ветер' if ru else '🌬️ Wind'
#             )

#             add(
#                 '  Максимальная скорость',
#                 '  Maximum speed',
#                 speed,
#                 unit,
#                 0,
#             )

#             add(
#                 '  Максимальные порывы',
#                 '  Maximum gusts',
#                 gusts,
#                 unit,
#                 0,
#             )

#             formatted_direction = format_wind_direction(
#                 direction,
#                 language,
#             )

#             if formatted_direction:
#                 label = (
#                     '  Направление'
#                     if ru
#                     else '  Direction'
#                 )

#                 lines.append(
#                     f'{label}: {formatted_direction}'
#                 )

#     if 'precipitation' in metrics:
#         amount = get_daily_value(
#             daily,
#             'precipitation_sum',
#             index,
#         )

#         probability = get_daily_value(
#             daily,
#             'precipitation_probability_max',
#             index,
#         )

#         hours = get_daily_value(
#             daily,
#             'precipitation_hours',
#             index,
#         )

#         if any(
#             value is not None
#             for value in (amount, probability, hours)
#         ):
#             lines.append(
#                 '🌧️ Осадки'
#                 if ru
#                 else '🌧️ Precipitation'
#             )

#             add(
#                 '  Количество за сутки',
#                 '  Daily total',
#                 amount,
#                 'мм' if ru else 'mm',
#             )

#             add(
#                 '  Максимальная вероятность',
#                 '  Maximum probability',
#                 probability,
#                 '%',
#                 0,
#             )

#             if not compact:
#                 add(
#                     '  Продолжительность',
#                     '  Duration',
#                     hours,
#                     'ч' if ru else 'h',
#                 )

#     hourly_metrics = (
#         (
#             'humidity',
#             'relative_humidity_2m',
#             '%',
#         ),
#         (
#             'cloud',
#             'cloud_cover',
#             '%',
#         ),
#         (
#             'pressure',
#             'pressure_msl',
#             'гПа' if ru else 'hPa',
#         ),
#     )

#     for metric, key, unit in hourly_metrics:
#         if metric not in metrics:
#             continue

#         average = get_hourly_average(
#             hourly,
#             day,
#             key,
#         )

#         minimum, maximum = get_hourly_range(
#             hourly,
#             day,
#             key,
#         )

#         if average is None:
#             continue

#         lines.append(
#             LABELS[metric][0 if ru else 1]
#         )

#         add(
#             '  Среднее за сутки',
#             '  Daily average',
#             average,
#             unit,
#             0,
#         )

#         if not compact:
#             add(
#                 '  Минимум',
#                 '  Minimum',
#                 minimum,
#                 unit,
#                 0,
#             )

#             add(
#                 '  Максимум',
#                 '  Maximum',
#                 maximum,
#                 unit,
#                 0,
#             )

#     if 'uv' in metrics:
#         uv = get_daily_value(
#             daily,
#             'uv_index_max',
#             index,
#         )

#         add(
#             '☀️ Максимальный УФ-индекс',
#             '☀️ Maximum UV index',
#             uv,
#         )

#     return lines


# def format_current_phenomena(
#     current: dict,
#     metrics: tuple,
#     language: str,
# ) -> list[str]:
#     """Оформляет текущий дождь, снег и грозу отдельно."""
#     ru = language == 'ru'
#     lines = []

#     for metric, key, unit, icon, title in (
#         (
#             'rain',
#             'rain',
#             'мм' if ru else 'mm',
#             '🌧️',
#             'Дождь' if ru else 'Rain',
#         ),
#         (
#             'snow',
#             'snowfall',
#             'см' if ru else 'cm',
#             '❄️',
#             'Снег' if ru else 'Snow',
#         ),
#     ):
#         if metric not in metrics:
#             continue

#         value = current.get(key)

#         if value is None:
#             lines.append(
#                 f'{icon} {title}: '
#                 + ('нет данных' if ru else 'no data')
#             )
#         else:
#             lines.append(
#                 f'{icon} {title}: '
#                 f'{format_value(value, unit)}'
#             )

#     if 'thunderstorm' in metrics:
#         code = current.get('weather_code')

#         if code is None:
#             status = 'нет данных' if ru else 'no data'

#         elif code in (95, 96, 99):
#             status = (
#                 'наблюдается'
#                 if ru
#                 else 'indicated'
#             )

#         else:
#             status = (
#                 'не отмечена'
#                 if ru
#                 else 'not indicated'
#             )

#         title = 'Гроза' if ru else 'Thunderstorm'

#         lines.append(
#             f'⚡ {title}: {status}'
#         )

#     return lines


# def format_phenomena(
#     daily: dict,
#     hourly: dict,
#     day: str,
#     index: int,
#     metrics: tuple,
#     language: str,
#     historical: bool,
# ) -> list[str]:
#     """Формирует ответы о дожде, снеге и грозе."""
#     ru = language == 'ru'
#     lines = []

#     phenomena = (
#         (
#             'rain',
#             'rain_sum',
#             'мм' if ru else 'mm',
#             '🌧️',
#         ),
#         (
#             'snow',
#             'snowfall_sum',
#             'см' if ru else 'cm',
#             '❄️',
#         ),
#         (
#             'thunderstorm',
#             'weather_code',
#             '',
#             '⚡',
#         ),
#     )

#     for metric, key, unit, icon in phenomena:
#         if metric not in metrics:
#             continue

#         titles = {
#             'rain': ('Дождь', 'Rain'),
#             'snow': ('Снег', 'Snow'),
#             'thunderstorm': ('Гроза', 'Thunderstorm'),
#         }

#         title = titles[metric][0 if ru else 1]
#         lines.append(f'{icon} {title}')

#         if metric == 'thunderstorm':
#             codes = get_hourly_values(
#                 hourly,
#                 day,
#                 'weather_code',
#             )

#             daily_code = get_daily_value(
#                 daily,
#                 'weather_code',
#                 index,
#             )

#             if not codes and daily_code is None:
#                 lines.append(
#                     '  Нет данных о грозах'
#                     if ru
#                     else '  Thunderstorm data unavailable'
#                 )
#                 continue

#             detected = any(
#                 code in (95, 96, 99)
#                 for code in codes
#             )

#             detected = (
#                 detected
#                 or daily_code in (95, 96, 99)
#             )

#             if detected:
#                 lines.append(
#                     '  Грозовая активность отмечена в данных'
#                     if ru
#                     else '  Thunderstorm activity indicated by the data'
#                 )

#             elif ru:
#                 lines.append(
#                     '  Гроза не отмечена в данных'
#                     if historical
#                     else '  По доступным данным гроза не ожидается'
#                 )

#             else:
#                 lines.append(
#                     '  No thunderstorm indicated by available data'
#                 )

#             hours = get_hourly_events(
#                 hourly,
#                 day,
#                 'thunderstorm',
#             )

#         else:
#             amount = get_daily_value(
#                 daily,
#                 key,
#                 index,
#             )

#             if amount is None:
#                 lines.append(
#                     '  Нет данных'
#                     if ru
#                     else '  Data unavailable'
#                 )
#                 continue

#             if amount > 0:
#                 label = (
#                     '  За сутки'
#                     if ru
#                     else '  Daily total'
#                 )

#                 lines.append(
#                     f'{label}: '
#                     f'{format_value(amount, unit)}'
#                 )

#             elif ru:
#                 lines.append(
#                     '  Не отмечен в данных'
#                     if historical
#                     else '  Не прогнозируется'
#                 )

#             else:
#                 lines.append(
#                     '  Not indicated by available data'
#                 )

#             hours = get_hourly_events(
#                 hourly,
#                 day,
#                 metric,
#             )

#         if metric in ('rain', 'snow'):
#             intervals = get_intensity_intervals(
#                 hourly,
#                 day,
#                 metric,
#                 language,
#             )

#             if intervals:
#                 unit_per_hour = (
#                     'мм/ч'
#                     if metric == 'rain' and ru
#                     else (
#                         'mm/h'
#                         if metric == 'rain'
#                         else 'см/ч' if ru else 'cm/h'
#                     )
#                 )

#                 lines.append(
#                     '  По часам (местное время):'
#                     if ru
#                     else '  Hourly intervals (local time):'
#                 )

#                 for period, level, peak in intervals:
#                     qualifier = 'до' if ru else 'up to'

#                     lines.append(
#                         f'  • {period} — {level}, '
#                         f'{qualifier} '
#                         f'{format_value(peak, unit_per_hour)}'
#                     )

#             elif hours:
#                 label = (
#                     '  Часы (местное время)'
#                     if ru
#                     else '  Hours (local time)'
#                 )

#                 lines.append(
#                     f'{label}: '
#                     f'{compact_event_hours(hours)}'
#                 )

#         elif hours:
#             label = (
#                 '  Часы (местное время)'
#                 if ru
#                 else '  Hours (local time)'
#             )

#             lines.append(
#                 f'{label}: '
#                 f'{compact_event_hours(hours)}'
#             )

#     return lines


# def format_weather(
#     city: dict,
#     query,
#     result: dict,
#     language: str,
# ) -> str:
#     """Составляет локализованный ответ о погоде."""
#     language = (
#         language
#         if language in MESSAGES
#         else 'en'
#     )

#     ru = language == 'ru'

#     metrics = tuple(
#         query.metrics or (
#             'temperature',
#             'feels_like',
#             'wind',
#             'precipitation',
#             'humidity',
#         )
#     )

#     city_name = city.get('name', '')
#     country = city.get('country', '')

#     location = escape(
#         ', '.join(
#             part
#             for part in (city_name, country)
#             if part
#         )
#     )

#     kind = result.get('kind')
#     raw_date = str(result.get('date', ''))

#     if kind == 'now':
#         heading = (
#             '🌤️ Погода сейчас'
#             if ru
#             else '🌤️ Current weather'
#         )

#     elif kind in ('week', 'weekend'):
#         heading = (
#             '🌤️ Прогноз погоды'
#             if ru
#             else '🌤️ Weather forecast'
#         )

#     else:
#         heading = (
#             '🌤️ Погода на выбранную дату'
#             if ru
#             else '🌤️ Weather for selected date'
#         )

#     lines = [
#         heading,
#         f'📍 {location}',
#     ]

#     if raw_date and kind not in ('week', 'weekend'):
#         try:
#             lines.append(
#                 f'📅 {format_date(raw_date, language)}'
#             )

#         except ValueError:
#             lines.append(
#                 f'📅 {raw_date}'
#             )

#     lines.append('━━━━━━━━━━━━━━━━━━')

#     if kind == 'now':
#         current = result.get('current') or {}

#         content = format_current(
#             current,
#             metrics,
#             language,
#         )

#         timestamp = current.get('time')

#         if timestamp:
#             lines.append(
#                 f"🕒 {'Время данных' if ru else 'Data time'}: "
#                 f'{str(timestamp)[11:16]}'
#             )

#             lines.append('')

#         lines.extend(content)

#         lines.extend(
#             format_current_phenomena(
#                 current,
#                 metrics,
#                 language,
#             )
#         )

#     else:
#         daily = result.get('daily') or {}
#         hourly = result.get('hourly') or {}
#         days = daily.get('time') or []

#         content = []

#         for index, day in enumerate(days):
#             if kind in ('week', 'weekend'):
#                 try:
#                     day_label = format_date(
#                         day,
#                         language,
#                     )

#                 except ValueError:
#                     day_label = str(day)

#                 content.append(
#                     f'📅 {day_label}'
#                 )

#             day_lines = format_daily(
#                 daily=daily,
#                 hourly=hourly,
#                 day=day,
#                 index=index,
#                 metrics=metrics,
#                 language=language,
#                 compact=kind in ('week', 'weekend'),
#             )

#             content.extend(day_lines)

#             content.extend(
#                 format_phenomena(
#                     daily,
#                     hourly,
#                     day,
#                     index,
#                     metrics,
#                     language,
#                     result.get('historical', False),
#                 )
#             )

#             if (
#                 kind in ('week', 'weekend')
#                 and index < len(days) - 1
#             ):
#                 content.extend([
#                     '',
#                     '────────────',
#                     '',
#                 ])

#         lines.extend(content)

#     if not content:
#         lines.append(
#             MESSAGES[language]['no_data']
#         )

#     # Сохраняем обязательную атрибуцию Open-Meteo
#     # и ссылку на лицензию данных.
#     attribution = (
#         '🌦️ Данные о погоде: '
#         if ru
#         else '🌦️ Weather data: '
#     ) + (
#         '<a href="https://open-meteo.com/">Open-Meteo</a> · '
#         '<a href="https://creativecommons.org/licenses/by/4.0/">'
#         'CC BY 4.0</a>'
#     )

#     lines.extend([
#         '',
#         '━━━━━━━━━━━━━━━━━━',
#         attribution,
#     ])

#     return '\n'.join(lines).strip()


"""Форматирование погодных данных для двуязычного бота Stormy.

Преобразует текущие, суточные и почасовые данные в сообщения
на русском и английском языках. Использует расчётные функции
и справочники локализации.

Не выполняет API-запросы и не управляет Telegram-диалогами.
"""

from datetime import datetime
from html import escape

from weather_analytics.bot.constants import (
    DAY_PERIODS,
    FULL_CIRCLE_DEGREES,
    THUNDERSTORM_CODES,
    WIND_SECTOR_DEGREES,
)
from weather_analytics.bot.messages import (
    LABELS,
    MESSAGES,
    MONTHS_EN,
    MONTHS_RU,
    WEEKDAYS_EN,
    WEEKDAYS_RU,
)
from weather_analytics.bot.weather_calculations import (
    compact_event_hours,
    get_daily_value,
    get_hourly_average,
    get_hourly_events,
    get_hourly_range,
    get_hourly_values,
    get_intensity_intervals,
    get_period_temperature,
)


def format_number(
    value,
    digits: int = 1,
    signed: bool = False,
) -> str:
    """Форматирует число с заданной точностью и знаком."""
    if value is None:
        return '—'

    number = round(float(value), digits)

    if number == 0:
        number = 0.0

    text = (
        f'{number:+.{digits}f}'
        if signed
        else f'{number:.{digits}f}'
    )

    return text.rstrip('0').rstrip('.') if digits else text


def format_value(
    value,
    unit: str = '',
    digits: int = 1,
    signed: bool = False,
) -> str:
    """Добавляет единицу измерения к числу."""
    return f'{format_number(value, digits, signed)} {unit}'.strip()


def format_date(value: str, language: str) -> str:
    """Преобразует ISO-дату в локализованный формат."""
    day = datetime.fromisoformat(str(value)).date()

    if language == 'ru':
        return (
            f'{WEEKDAYS_RU[day.weekday()].capitalize()}, '
            f'{day.day} {MONTHS_RU[day.month]} {day.year} года'
        )

    return (
        f'{WEEKDAYS_EN[day.weekday()]}, '
        f'{MONTHS_EN[day.month]} {day.day}, {day.year}'
    )


def _local_time(value: str) -> str:
    """Извлекает местное время из ISO-метки."""
    return datetime.fromisoformat(str(value)).strftime('%H:%M')


def _metric_line(
    label: str,
    value,
    unit: str = '',
    digits: int = 1,
    signed: bool = False,
) -> str | None:
    """Формирует строку показателя при наличии значения."""
    if value is None:
        return None

    return f'{label}: {format_value(value, unit, digits, signed)}'


def _add_metric(
    lines: list[str],
    label_ru: str,
    label_en: str,
    value,
    language: str,
    unit: str = '',
    digits: int = 1,
    signed: bool = False,
) -> None:
    """Добавляет локализованную строку показателя."""
    label = label_ru if language == 'ru' else label_en
    line = _metric_line(label, value, unit, digits, signed)

    if line is not None:
        lines.append(line)


def format_current(
    current: dict,
    metrics: tuple,
    language: str,
) -> list[str]:
    """Формирует строки текущих погодных показателей."""
    ru = language == 'ru'
    lines = []

    fields = {
        'temperature': 'temperature_2m',
        'feels_like': 'apparent_temperature',
        'wind': 'wind_speed_10m',
        'rain': 'rain',
        'snow': 'snowfall',
        'precipitation': 'precipitation',
        'humidity': 'relative_humidity_2m',
        'cloud': 'cloud_cover',
        'pressure': 'pressure_msl',
        'uv': 'uv_index',
    }

    decimal_metrics = {
        'temperature', 'feels_like', 'rain',
        'snow', 'precipitation', 'uv',
    }

    for metric in metrics:
        if metric not in LABELS or metric not in fields:
            continue

        value = current.get(fields.get(metric))
        label_ru, label_en, unit = LABELS[metric]

        if not ru:
            unit = {
                'км/ч': 'km/h',
                'мм': 'mm',
                'гПа': 'hPa',
            }.get(unit, unit)

        _add_metric(
            lines,
            label_ru,
            label_en,
            value,
            language,
            unit,
            digits=1 if metric in decimal_metrics else 0,
            signed=metric in ('temperature', 'feels_like'),
        )

    return lines


def format_wind_direction(value, language: str) -> str | None:
    """Преобразует направление ветра в сторону света и стрелку."""
    if value is None:
        return None

    # Метеорологическое направление указывает, откуда дует ветер.
    names_ru = (
        'С (северный)', 'СВ (северо-восточный)',
        'В (восточный)', 'ЮВ (юго-восточный)',
        'Ю (южный)', 'ЮЗ (юго-западный)',
        'З (западный)', 'СЗ (северо-западный)',
    )
    names_en = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')

    # Стрелка показывает движение воздуха в противоположную сторону.
    arrows = ('↓', '↙', '←', '↖', '↑', '↗', '→', '↘')

    degrees = float(value) % FULL_CIRCLE_DEGREES
    sector = int(
        (degrees + WIND_SECTOR_DEGREES / 2) // WIND_SECTOR_DEGREES
    ) % len(arrows)

    names = names_ru if language == 'ru' else names_en
    return f'{names[sector]} {arrows[sector]}'


def _format_temperature(
    daily: dict,
    hourly: dict,
    day: str,
    index: int,
    language: str,
    compact: bool,
) -> list[str]:
    """Формирует минимальную, максимальную и периодную температуру."""
    minimum = get_daily_value(daily, 'temperature_2m_min', index)
    maximum = get_daily_value(daily, 'temperature_2m_max', index)

    if minimum is None and maximum is None:
        return []

    ru = language == 'ru'
    lines = ['🌡️ Температура' if ru else '🌡️ Temperature']

    for label_ru, label_en, value in (
        ('  Минимальная', '  Minimum', minimum),
        ('  Максимальная', '  Maximum', maximum),
    ):
        _add_metric(
            lines, label_ru, label_en, value,
            language, '°C', signed=True,
        )

    if not compact:
        for start_hour, end_hour, label_ru, label_en in DAY_PERIODS:
            value = get_period_temperature(
                hourly, day, start_hour, end_hour,
            )
            _add_metric(
                lines, label_ru, label_en, value,
                language, '°C', signed=True,
            )

    return lines


def _format_feels_like(
    daily: dict,
    hourly: dict,
    day: str,
    index: int,
    language: str,
) -> list[str]:
    """Формирует минимальную и максимальную ощущаемую температуру."""
    minimum, maximum = get_hourly_range(
        hourly, day, 'apparent_temperature',
    )

    if minimum is None:
        minimum = get_daily_value(
            daily, 'apparent_temperature_min', index,
        )
    if maximum is None:
        maximum = get_daily_value(
            daily, 'apparent_temperature_max', index,
        )

    if minimum is None and maximum is None:
        return []

    lines = [
        '🤗 Ощущается как'
        if language == 'ru'
        else '🤗 Feels like'
    ]

    for label_ru, label_en, value in (
        ('  Минимальная', '  Minimum', minimum),
        ('  Максимальная', '  Maximum', maximum),
    ):
        _add_metric(
            lines, label_ru, label_en, value,
            language, '°C', signed=True,
        )

    return lines


def _format_wind(
    daily: dict,
    index: int,
    language: str,
) -> list[str]:
    """Формирует скорость, порывы и направление ветра."""
    speed = get_daily_value(daily, 'wind_speed_10m_max', index)
    gusts = get_daily_value(daily, 'wind_gusts_10m_max', index)
    direction = get_daily_value(
        daily, 'wind_direction_10m_dominant', index,
    )

    if all(value is None for value in (speed, gusts, direction)):
        return []

    ru = language == 'ru'
    lines = ['🌬️ Ветер' if ru else '🌬️ Wind']
    unit = 'км/ч' if ru else 'km/h'

    for label_ru, label_en, value in (
        ('  Максимальная скорость', '  Maximum speed', speed),
        ('  Максимальные порывы', '  Maximum gusts', gusts),
    ):
        _add_metric(
            lines, label_ru, label_en, value,
            language, unit, digits=0,
        )

    formatted = format_wind_direction(direction, language)
    if formatted:
        label = '  Направление' if ru else '  Direction'
        lines.append(f'{label}: {formatted}')

    return lines


def _format_precipitation(
    daily: dict,
    index: int,
    language: str,
    compact: bool,
) -> list[str]:
    """Формирует суточные осадки, вероятность и продолжительность."""
    amount = get_daily_value(daily, 'precipitation_sum', index)
    probability = get_daily_value(
        daily, 'precipitation_probability_max', index,
    )
    hours = get_daily_value(daily, 'precipitation_hours', index)

    if all(value is None for value in (amount, probability, hours)):
        return []

    ru = language == 'ru'
    lines = ['🌧️ Осадки' if ru else '🌧️ Precipitation']

    _add_metric(
        lines, '  Количество за сутки', '  Daily total',
        amount, language, 'мм' if ru else 'mm',
    )
    _add_metric(
        lines, '  Максимальная вероятность', '  Maximum probability',
        probability, language, '%', digits=0,
    )

    if not compact:
        _add_metric(
            lines, '  Продолжительность', '  Duration',
            hours, language, 'ч' if ru else 'h',
        )

    return lines


def _format_hourly_metrics(
    hourly: dict,
    day: str,
    metrics: tuple,
    language: str,
    compact: bool,
) -> list[str]:
    """Формирует влажность, облачность и атмосферное давление."""
    ru = language == 'ru'
    lines = []

    fields = (
        ('humidity', 'relative_humidity_2m', '%'),
        ('cloud', 'cloud_cover', '%'),
        ('pressure', 'pressure_msl', 'гПа' if ru else 'hPa'),
    )

    for metric, key, unit in fields:
        if metric not in metrics:
            continue

        average = get_hourly_average(hourly, day, key)
        if average is None:
            continue

        minimum, maximum = get_hourly_range(hourly, day, key)
        lines.append(LABELS[metric][0 if ru else 1])

        values = [('  Среднее за сутки', '  Daily average', average)]

        if not compact:
            values.extend((
                ('  Минимум', '  Minimum', minimum),
                ('  Максимум', '  Maximum', maximum),
            ))

        for label_ru, label_en, value in values:
            _add_metric(
                lines, label_ru, label_en, value,
                language, unit, digits=0,
            )

    return lines


def format_daily(
    daily: dict,
    hourly: dict,
    day: str,
    index: int,
    metrics: tuple,
    language: str,
    compact: bool = False,
) -> list[str]:
    """Оформляет суточные показатели выбранных погодных метрик."""
    lines = []

    if 'temperature' in metrics:
        lines.extend(
            _format_temperature(
                daily, hourly, day, index, language, compact,
            )
        )

    if 'feels_like' in metrics:
        lines.extend(
            _format_feels_like(daily, hourly, day, index, language)
        )

    if 'wind' in metrics:
        lines.extend(_format_wind(daily, index, language))

    if 'precipitation' in metrics:
        lines.extend(
            _format_precipitation(daily, index, language, compact)
        )

    lines.extend(
        _format_hourly_metrics(
            hourly, day, metrics, language, compact,
        )
    )

    if 'uv' in metrics:
        _add_metric(
            lines,
            '☀️ Максимальный УФ-индекс',
            '☀️ Maximum UV index',
            get_daily_value(daily, 'uv_index_max', index),
            language,
        )

    return lines


def format_current_phenomena(
    current: dict,
    metrics: tuple,
    language: str,
) -> list[str]:
    """Оформляет текущий дождь, снег и грозу отдельно."""
    ru = language == 'ru'
    lines = []

    for metric, key, unit, icon, title in (
        ('rain', 'rain', 'мм' if ru else 'mm', '🌧️',
         'Дождь' if ru else 'Rain'),
        ('snow', 'snowfall', 'см' if ru else 'cm', '❄️',
         'Снег' if ru else 'Snow'),
    ):
        if metric not in metrics:
            continue

        value = current.get(key)
        text = (
            format_value(value, unit)
            if value is not None
            else 'нет данных' if ru else 'no data'
        )
        lines.append(f'{icon} {title}: {text}')

    if 'thunderstorm' in metrics:
        code = current.get('weather_code')

        if code is None:
            status = 'нет данных' if ru else 'no data'
        elif code in THUNDERSTORM_CODES:
            status = 'наблюдается' if ru else 'indicated'
        else:
            status = 'не отмечена' if ru else 'not indicated'

        title = 'Гроза' if ru else 'Thunderstorm'
        lines.append(f'⚡ {title}: {status}')

    return lines


def _format_intensity(
    hourly: dict,
    day: str,
    metric: str,
    language: str,
) -> list[str]:
    """Формирует почасовые интервалы интенсивности дождя или снега."""
    # В запросах бота метрика называется snow,
    # а соответствующее поле Open-Meteo — snowfall.
    api_metric = 'snowfall' if metric == 'snow' else metric

    intervals = get_intensity_intervals(
        hourly,
        day,
        api_metric,
        language,
    )

    if not intervals:
        return []

    ru = language == 'ru'
    unit = (
        ('мм/ч' if ru else 'mm/h')
        if metric == 'rain'
        else ('см/ч' if ru else 'cm/h')
    )

    lines = [
        '  По часам (местное время):'
        if ru
        else '  Hourly intervals (local time):'
    ]

    for period, level, peak in intervals:
        qualifier = 'до' if ru else 'up to'
        lines.append(
            f'  • {period} — {level}, {qualifier} '
            f'{format_value(peak, unit)}'
        )

    return lines


def format_phenomena(
    daily: dict,
    hourly: dict,
    day: str,
    index: int,
    metrics: tuple,
    language: str,
    historical: bool,
) -> list[str]:
    """Формирует ответы о дожде, снеге и грозе."""
    ru = language == 'ru'
    lines = []

    phenomena = (
        ('rain', 'rain_sum', 'мм' if ru else 'mm', '🌧️'),
        ('snow', 'snowfall_sum', 'см' if ru else 'cm', '❄️'),
        ('thunderstorm', 'weather_code', '', '⚡'),
    )
    titles = {
        'rain': ('Дождь', 'Rain'),
        'snow': ('Снег', 'Snow'),
        'thunderstorm': ('Гроза', 'Thunderstorm'),
    }

    for metric, key, unit, icon in phenomena:
        if metric not in metrics:
            continue

        lines.append(f'{icon} {titles[metric][0 if ru else 1]}')

        if metric == 'thunderstorm':
            codes = get_hourly_values(hourly, day, 'weather_code')
            daily_code = get_daily_value(daily, 'weather_code', index)

            if not codes and daily_code is None:
                lines.append(
                    '  Нет данных о грозах'
                    if ru
                    else '  Thunderstorm data unavailable'
                )
                continue

            detected = (
                any(code in THUNDERSTORM_CODES for code in codes)
                or daily_code in THUNDERSTORM_CODES
            )

            if detected:
                lines.append(
                    '  Грозовая активность отмечена в данных'
                    if ru
                    else '  Thunderstorm activity indicated by the data'
                )
            elif ru:
                lines.append(
                    '  Гроза не отмечена в данных'
                    if historical
                    else '  По доступным данным гроза не ожидается'
                )
            else:
                lines.append(
                    '  No thunderstorm indicated by available data'
                )

        else:
            amount = get_daily_value(daily, key, index)

            if amount is None:
                lines.append(
                    '  Нет суточных данных'
                    if ru
                    else '  Daily data unavailable'
                )
            elif amount > 0:
                label = '  За сутки' if ru else '  Daily total'
                lines.append(
                    f'{label}: {format_value(amount, unit)}'
                )
            elif ru:
                lines.append(
                    '  Не отмечен в данных'
                    if historical
                    else '  Не прогнозируется'
                )
            else:
                lines.append(
                    '  Not indicated by available data'
                )

        # Для снегопада используем имя поля Open-Meteo.
        api_metric = 'snowfall' if metric == 'snow' else metric
        hours = get_hourly_events(hourly, day, api_metric)

        if metric in ('rain', 'snow'):
            intervals = _format_intensity(
                hourly, day, metric, language,
            )
            if intervals:
                lines.extend(intervals)
                continue

        if hours:
            label = (
                '  Часы (местное время)'
                if ru
                else '  Hours (local time)'
            )
            lines.append(
                f'{label}: {compact_event_hours(hours)}'
            )

    return lines


def format_weather(
    city: dict,
    query,
    result: dict,
    language: str,
) -> str:
    """Составляет локализованный ответ о погоде."""
    language = language if language in MESSAGES else 'en'
    ru = language == 'ru'

    metrics = tuple(query.metrics or (
        'temperature', 'feels_like', 'wind',
        'precipitation', 'humidity',
    ))

    location = escape(', '.join(
        part
        for part in (city.get('name', ''), city.get('country', ''))
        if part
    ))

    kind = result.get('kind')
    raw_date = str(result.get('date', ''))

    if kind == 'now':
        heading = '🌤️ Погода сейчас' if ru else '🌤️ Current weather'
    elif kind in ('week', 'weekend'):
        heading = '🌤️ Прогноз погоды' if ru else '🌤️ Weather forecast'
    else:
        heading = (
            '🌤️ Погода на выбранную дату'
            if ru else '🌤️ Weather for selected date'
        )

    lines = [heading, f'📍 {location}']

    if raw_date and kind not in ('week', 'weekend'):
        try:
            lines.append(f'📅 {format_date(raw_date, language)}')
        except ValueError:
            lines.append(f'📅 {raw_date}')

    lines.append('━━━━━━━━━━━━━━━━━━')

    if kind == 'now':
        current = result.get('current') or {}

        content = format_current(
            current,
            metrics,
            language,
        )
        content.extend(
            format_current_phenomena(
                current,
                metrics,
                language,
            )
        )

        timestamp = current.get('time')
        if timestamp:
            lines.append(
                f"🕒 {'Время данных' if ru else 'Data time'}: "
                f'{_local_time(timestamp)}'
            )
            lines.append('')

        lines.extend(content)

    else:
        daily = result.get('daily') or {}
        hourly = result.get('hourly') or {}
        days = daily.get('time') or []
        content = []

        for index, day in enumerate(days):
            if kind in ('week', 'weekend'):
                try:
                    day_label = format_date(day, language)
                except ValueError:
                    day_label = str(day)

                content.append(f'📅 {day_label}')

            content.extend(
                format_daily(
                    daily, hourly, day, index, metrics,
                    language, compact=kind in ('week', 'weekend'),
                )
            )
            content.extend(
                format_phenomena(
                    daily, hourly, day, index, metrics,
                    language, result.get('historical', False),
                )
            )

            if kind in ('week', 'weekend') and index < len(days) - 1:
                content.extend(['', '────────────', ''])

        lines.extend(content)

    if not content:
        lines.append(MESSAGES[language]['no_data'])

    # Обязательная атрибуция источника и лицензии данных.
    attribution = (
        '🌦️ Данные о погоде: '
        if ru else '🌦️ Weather data: '
    ) + (
        '<a href="https://open-meteo.com/">Open-Meteo</a> · '
        '<a href="https://creativecommons.org/licenses/by/4.0/">'
        'CC BY 4.0</a>'
    )

    lines.extend(['', '━━━━━━━━━━━━━━━━━━', attribution])
    return '\n'.join(lines).strip()

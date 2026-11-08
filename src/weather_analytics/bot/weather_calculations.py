# """Расчёты и агрегация погодных данных для Telegram-бота Stormy.

# Содержит функции извлечения суточных и почасовых показателей,
# вычисления средних и экстремальных значений, определения
# интенсивности осадков и объединения погодных явлений
# в последовательные временные интервалы.

# Не зависит от Telegram, локализации сообщений и форматирования
# погодных ответов.
# """

# from datetime import datetime, timedelta
# from statistics import mean


# def get_daily_value(
#     daily: dict,
#     key: str,
#     index: int,
# ):
#     """Безопасно возвращает суточное значение по индексу."""
#     values = daily.get(key) or []

#     return values[index] if index < len(values) else None


# def get_hourly_values(
#     hourly: dict,
#     day: str,
#     key: str,
# ) -> list:
#     """Собирает доступные почасовые значения для выбранной даты."""
#     times = hourly.get('time') or []
#     values = hourly.get(key) or []

#     return [
#         value
#         for timestamp, value in zip(times, values)
#         if str(timestamp)[:10] == day and value is not None
#     ]


# def get_hourly_average(
#     hourly: dict,
#     day: str,
#     key: str,
# ):
#     """Вычисляет среднее значение показателя за выбранные сутки."""
#     values = get_hourly_values(hourly, day, key)

#     return mean(values) if values else None


# def get_hourly_range(
#     hourly: dict,
#     day: str,
#     key: str,
# ):
#     """Возвращает минимальное и максимальное почасовые значения."""
#     values = get_hourly_values(hourly, day, key)

#     return (min(values), max(values)) if values else (None, None)


# def get_period_temperature(
#     hourly: dict,
#     day: str,
#     start_hour: int,
#     end_hour: int,
# ):
#     """Вычисляет среднюю температуру за заданные часы местных суток."""
#     times = hourly.get('time') or []
#     temperatures = hourly.get('temperature_2m') or []

#     # Отбираем только значения за нужную дату и часы.
#     # Временные метки Open-Meteo здесь уже представлены
#     # в местном времени выбранного населённого пункта.
#     values = [
#         temperature
#         for timestamp, temperature in zip(times, temperatures)
#         if (
#             str(timestamp)[:10] == day
#             and start_hour <= int(str(timestamp)[11:13]) <= end_hour
#             and temperature is not None
#         )
#     ]

#     return mean(values) if values else None


# def get_hourly_events(
#     hourly: dict,
#     day: str,
#     metric: str,
# ) -> list[str]:
#     """Возвращает местные часы с дождём, снегом или грозой."""
#     times = hourly.get('time') or []
#     values = hourly.get(
#         'weather_code' if metric == 'thunderstorm' else metric
#     ) or []

#     result = []

#     for timestamp, value in zip(times, values):
#         if str(timestamp)[:10] != day or value is None:
#             continue

#         # Для грозы используем коды погодных явлений.
#         # Для дождя и снега проверяем положительное количество.
#         active = (
#             value in (95, 96, 99)
#             if metric == 'thunderstorm'
#             else value > 0
#         )

#         if active:
#             result.append(str(timestamp)[11:16])

#     return result


# def compact_event_hours(hours: list[str]) -> str:
#     """Объединяет последовательные часы явления в компактные интервалы."""
#     if not hours:
#         return ''

#     # Удаляем повторы и сортируем часы в пределах суток.
#     minutes = sorted({
#         int(hour[:2]) * 60 + int(hour[3:5])
#         for hour in hours
#     })

#     intervals = []
#     start = end = minutes[0]

#     for minute in minutes[1:]:
#         if minute == end + 60:
#             end = minute
#         else:
#             intervals.append((start, end))
#             start = end = minute

#     intervals.append((start, end))

#     def clock(value: int) -> str:
#         """Преобразует минуты от полуночи в местное время ЧЧ:ММ."""
#         return f'{value // 60:02d}:{value % 60:02d}'

#     return ', '.join(
#         (
#             clock(start)
#             if start == end
#             else f'{clock(start)}–{clock(end)}'
#         )
#         for start, end in intervals
#     )


# def intensity_level(
#     amount: float,
#     metric: str,
#     language: str,
# ) -> str:
#     """Даёт ориентировочную оценку интенсивности дождя и снега.

#     Для дождя используются миллиметры за час,
#     для снега — сантиметры за час.

#     Пороговые значения являются ориентировочными,
#     а не официальными уровнями погодной опасности.
#     """
#     low, high = (
#         (2.5, 7.5)
#         if metric == 'rain'
#         else (0.5, 2.0)
#     )

#     labels = (
#         ('слабый', 'умеренный', 'сильный')
#         if language == 'ru'
#         else ('light', 'moderate', 'heavy')
#     )

#     return (
#         labels[0]
#         if amount < low
#         else labels[1]
#         if amount < high
#         else labels[2]
#     )


# def get_intensity_intervals(
#     hourly: dict,
#     day: str,
#     metric: str,
#     language: str = 'ru',
# ) -> list[tuple[str, str, float]]:
#     """Объединяет соседние часы одинаковой интенсивности.

#     Для каждого интервала сохраняет время начала и окончания,
#     категорию интенсивности и максимальное часовое значение.

#     Args:
#         hourly: Почасовые данные Open-Meteo.
#         day: Дата в формате YYYY-MM-DD.
#         metric: Дождь (rain) или снег (snowfall).
#         language: Язык названия категории интенсивности.

#     Returns:
#         Список кортежей (интервал, категория, пиковое значение).
#     """
#     times = hourly.get('time') or []
#     values = hourly.get(metric) or []
#     showers = hourly.get('showers') or []

#     observations = []

#     # Для дождя сохраняем существующую формулу:
#     # обычный дождь плюс ливневые осадки.
#     # Семантику этих полей отдельно проверим при ревизии.
#     for index, (timestamp, value) in enumerate(
#         zip(times, values)
#     ):
#         if str(timestamp)[:10] != day:
#             continue

#         if metric == 'rain':
#             shower = (
#                 showers[index]
#                 if index < len(showers)
#                 else None
#             )

#             if value is None and shower is None:
#                 continue

#             amount = (value or 0) + (shower or 0)

#         else:
#             if value is None:
#                 continue

#             amount = value

#         if amount > 0:
#             moment = datetime.fromisoformat(
#                 str(timestamp)
#             )

#             observations.append((
#                 moment,
#                 intensity_level(
#                     amount,
#                     metric,
#                     language,
#                 ),
#                 amount,
#             ))

#     if not observations:
#         return []

#     # Новый интервал начинается при разрыве во времени
#     # или при изменении категории интенсивности.
#     groups = []

#     start = end = observations[0][0]
#     level, peak = observations[0][1:]

#     for moment, next_level, amount in observations[1:]:
#         if (
#             moment - end == timedelta(hours=1)
#             and next_level == level
#         ):
#             end = moment
#             peak = max(peak, amount)

#         else:
#             groups.append((
#                 start,
#                 end,
#                 level,
#                 peak,
#             ))

#             start = end = moment
#             level, peak = next_level, amount

#     groups.append((
#         start,
#         end,
#         level,
#         peak,
#     ))

#     return [
#         (
#             (
#                 start.strftime('%H:%M')
#                 if start == end
#                 else (
#                     f'{start.strftime("%H:%M")}'
#                     f'–{end.strftime("%H:%M")}'
#                 )
#             ),
#             level,
#             peak,
#         )
#         for start, end, level, peak in groups
#     ]


"""Расчёты и агрегация погодных данных для Telegram-бота Stormy.

Содержит функции извлечения суточных и почасовых показателей,
вычисления средних и экстремальных значений, определения
интенсивности осадков и объединения погодных явлений
в последовательные временные интервалы.

Не зависит от Telegram и форматирования погодных ответов.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from weather_analytics.bot.constants import (
    MINUTES_PER_HOUR,
    RAIN_INTENSITY_THRESHOLDS,
    SNOW_INTENSITY_THRESHOLDS,
    THUNDERSTORM_CODES,
)


def get_daily_value(
    daily: dict,
    key: str,
    index: int,
):
    """Безопасно возвращает суточное значение по индексу."""
    values = daily.get(key) or []

    return values[index] if 0 <= index < len(values) else None


def _day_observations(
    hourly: dict,
    day: str,
    key: str,
) -> Iterator[tuple[int, datetime, Any]]:
    """Перебирает почасовые наблюдения за выбранную дату.

    Args:
        hourly: Почасовые данные Open-Meteo.
        day: Дата в формате YYYY-MM-DD.
        key: Название погодного показателя.

    Yields:
        Индекс наблюдения, местную временную метку
        и соответствующее значение показателя.

    Notes:
        Open-Meteo возвращает ISO-время в часовом поясе
        запроса. При стандартном ISO-формате переходы
        летнего и зимнего времени могут не учитываться.
    """
    times = hourly.get('time') or []
    values = hourly.get(key) or []

    for index, (timestamp, value) in enumerate(zip(times, values, strict=True)):
        moment = datetime.fromisoformat(str(timestamp))

        if moment.date().isoformat() == day:
            yield index, moment, value


def get_hourly_values(
    hourly: dict,
    day: str,
    key: str,
) -> list:
    """Собирает доступные почасовые значения за выбранную дату."""
    return [
        value
        for _, _, value in _day_observations(hourly, day, key)
        if value is not None
    ]


def get_hourly_average(
    hourly: dict,
    day: str,
    key: str,
):
    """Вычисляет среднее значение показателя за выбранные сутки."""
    values = get_hourly_values(hourly, day, key)

    return mean(values) if values else None


def get_hourly_range(
    hourly: dict,
    day: str,
    key: str,
):
    """Возвращает минимальное и максимальное почасовые значения."""
    values = get_hourly_values(hourly, day, key)

    return (min(values), max(values)) if values else (None, None)


def get_period_temperature(
    hourly: dict,
    day: str,
    start_hour: int,
    end_hour: int,
):
    """Вычисляет среднюю температуру за заданные часы суток.

    Границы интервала включаются в расчёт.
    """
    values = [
        temperature
        for _, moment, temperature in _day_observations(
            hourly,
            day,
            'temperature_2m',
        )
        if (temperature is not None and start_hour <= moment.hour <= end_hour)
    ]

    return mean(values) if values else None


def get_hourly_events(
    hourly: dict,
    day: str,
    metric: str,
) -> list[str]:
    """Возвращает местные часы с дождём, снегом или грозой.

    Для дождя учитывает обычные и ливневые осадки.
    Для грозы использует коды погодных явлений WMO.
    """
    key = 'weather_code' if metric == 'thunderstorm' else metric
    showers = hourly.get('showers') or []

    result = []

    for index, moment, value in _day_observations(
        hourly,
        day,
        key,
    ):
        if metric == 'thunderstorm':
            active = value in THUNDERSTORM_CODES

        elif metric == 'rain':
            shower = showers[index] if index < len(showers) else None

            active = (value is not None or shower is not None) and (value or 0) + (
                shower or 0
            ) > 0

        else:
            active = value is not None and value > 0

        if active:
            result.append(moment.strftime('%H:%M'))

    return result


def compact_event_hours(hours: list[str]) -> str:
    """Объединяет последовательные часы явления в интервалы.

    Интервал отражает первую и последнюю временные метки
    наблюдений, а не точное начало и окончание явления.
    """
    if not hours:
        return ''

    # Преобразуем часы в минуты от полуночи,
    # удаляем повторяющиеся значения и сортируем.
    minutes = sorted(
        {
            int(hour) * MINUTES_PER_HOUR + int(minute)
            for value in hours
            for hour, minute in [value.split(':')]
        }
    )

    intervals = []
    start = end = minutes[0]

    for minute in minutes[1:]:
        if minute == end + MINUTES_PER_HOUR:
            end = minute
        else:
            intervals.append((start, end))
            start = end = minute

    intervals.append((start, end))

    def clock(value: int) -> str:
        """Преобразует минуты от полуночи в формат ЧЧ:ММ."""
        hour, minute = divmod(value, MINUTES_PER_HOUR)
        return f'{hour:02d}:{minute:02d}'

    return ', '.join(
        (clock(start) if start == end else f'{clock(start)}–{clock(end)}')
        for start, end in intervals
    )


def intensity_level(
    amount: float,
    metric: str,
    language: str,
) -> str:
    """Определяет ориентировочную интенсивность дождя или снега.

    Для дождя используются миллиметры за час,
    для снега — сантиметры за час.

    Пороги не являются официальными уровнями
    метеорологической опасности.
    """
    low, high = (
        RAIN_INTENSITY_THRESHOLDS if metric == 'rain' else SNOW_INTENSITY_THRESHOLDS
    )

    labels = (
        ('слабый', 'умеренный', 'сильный')
        if language == 'ru'
        else ('light', 'moderate', 'heavy')
    )

    if amount < low:
        return labels[0]

    if amount < high:
        return labels[1]

    return labels[2]


def get_intensity_intervals(
    hourly: dict,
    day: str,
    metric: str,
    language: str = 'ru',
) -> list[tuple[str, str, float]]:
    """Объединяет соседние часы одинаковой интенсивности.

    Для дождя суммирует обычные и ливневые осадки.
    Для снега использует часовое количество snowfall.

    Args:
        hourly: Почасовые данные Open-Meteo.
        day: Дата в формате YYYY-MM-DD.
        metric: Дождь (rain) или снег (snowfall).
        language: Язык названия категории интенсивности.

    Returns:
        Список кортежей (временной интервал, категория
        интенсивности, максимальное часовое значение).
    """
    showers = hourly.get('showers') or []
    observations = []

    # Собираем наблюдения с положительным количеством осадков.
    for index, moment, value in _day_observations(
        hourly,
        day,
        metric,
    ):
        if metric == 'rain':
            shower = showers[index] if index < len(showers) else None

            if value is None and shower is None:
                continue

            # Rain и showers — отдельные составляющие
            # жидких осадков по документации Open-Meteo.
            amount = (value or 0) + (shower or 0)

        else:
            if value is None:
                continue

            amount = value

        if amount > 0:
            observations.append(
                (
                    moment,
                    intensity_level(amount, metric, language),
                    amount,
                )
            )

    if not observations:
        return []

    # Объединяем соседние наблюдения одной интенсивности.
    # Разрыв во времени или смена категории начинает
    # новый интервал.
    groups = []

    start = end = observations[0][0]
    level, peak = observations[0][1:]

    for moment, next_level, amount in observations[1:]:
        if moment - end == timedelta(hours=1) and next_level == level:
            end = moment
            peak = max(peak, amount)

        else:
            groups.append((start, end, level, peak))

            start = end = moment
            level, peak = next_level, amount

    groups.append((start, end, level, peak))

    return [
        (
            (
                start.strftime('%H:%M')
                if start == end
                else (f'{start.strftime("%H:%M")}–{end.strftime("%H:%M")}')
            ),
            level,
            peak,
        )
        for start, end, level, peak in groups
    ]

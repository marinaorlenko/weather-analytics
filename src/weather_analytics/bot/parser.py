"""Разбор русских и английских погодных запросов Stormy.

Определяет населённый пункт, погодные показатели, период,
календарную дату и временную направленность запроса.

Не обращается к Open-Meteo и не проверяет существование города.
Даты без года сохраняет для последующего разрешения
в часовом поясе выбранного населённого пункта.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from weather_analytics.bot.constants import LEAP_REFERENCE_YEAR
from weather_analytics.bot.parser_patterns import (
    CITY_END,
    CITY_NAME,
    CITY_PREPOSITION,
    CITY_TIME_WORDS,
    CITY_WEATHER_WORDS,
    CURRENT_PERIOD,
    EN_MONTHS,
    EN_WORD_DATE,
    FUTURE_INTENT,
    ISO_DATE,
    METRICS,
    NUMERIC_DATE,
    PAST_INTENT,
    RELATIVE_DATES,
    RU_MONTHS,
    RU_WORD_DATE,
    WEEK_PERIOD,
    WEEKDAYS,
    WEEKEND_PERIOD,
)


@dataclass(frozen=True)
class WeatherQuery:
    """Хранит параметры пользовательского погодного запроса.

    Attributes:
        city: Предполагаемое название населённого пункта.
        language: Язык запроса.
        metrics: Запрошенные погодные показатели.
        target_date: Полная календарная дата, если год известен.
        relative_days: Смещение относительно локальной даты города.
        weekday: Номер запрошенного дня недели.
        period: Тип периода: now, day, week или weekend.
        explicit_date: Признак явного указания даты или дня недели.
        day: День месяца для даты без года.
        month: Месяц для даты без года.
        time_intent: Направленность: past, future или unspecified.
    """

    city: str | None
    language: str
    metrics: tuple[str, ...]
    target_date: date | None
    relative_days: int | None
    weekday: int | None
    period: str
    explicit_date: bool
    day: int | None = None
    month: int | None = None
    time_intent: str = 'unspecified'


def extract_calendar_date(
    lowered: str,
) -> tuple[date | None, int | None, int | None]:
    """Извлекает календарную дату без подстановки текущего года.

    Args:
        lowered: Нормализованный текст пользовательского запроса.

    Returns:
        Полную дату либо отдельные день и месяц.

    Raises:
        ValueError: Если дата с указанным годом некорректна
            или день и месяц не образуют допустимую дату.
    """
    iso = ISO_DATE.search(lowered)
    numeric = NUMERIC_DATE.search(lowered)
    words_ru = RU_WORD_DATE.search(lowered)
    words_en = EN_WORD_DATE.search(lowered)

    if not any((iso, numeric, words_ru, words_en)):
        return None, None, None

    year: int | None

    try:
        if iso:
            year_str, month_str, day_str = iso.groups()
            return (
                date(int(year_str), int(month_str), int(day_str)),
                None,
                None,
            )

        if numeric:
            day_str, month_str, year_str = numeric.groups()
            day = int(day_str)
            month = int(month_str)
            year = int(year_str) if year_str else None

        elif words_ru:
            day_str, month_name, year_str = words_ru.groups()
            day = int(day_str)
            month = RU_MONTHS[month_name]
            year = int(year_str) if year_str else None

        elif words_en:
            month_name, day_str, year_str = words_en.groups()
            day = int(day_str)
            month = EN_MONTHS[month_name]
            year = int(year_str) if year_str else None

        else:
            return None, None, None

        if year is not None:
            return date(year, month, day), None, None

        # Проверяем корректность дня и месяца, включая 29 февраля,
        # не выбирая конкретный год пользовательского запроса.
        date(LEAP_REFERENCE_YEAR, month, day)

        return None, day, month

    except ValueError as exc:
        raise ValueError('invalid_date') from exc


def detect_time_intent(lowered: str) -> str:
    """Определяет направленность запроса по явным выражениям.

    Args:
        lowered: Нормализованный текст запроса.

    Returns:
        past, future или unspecified.
    """
    past = bool(PAST_INTENT.search(lowered))
    future = bool(FUTURE_INTENT.search(lowered))

    # При противоречивых признаках не пытаемся угадать
    # намерение пользователя.
    if past == future:
        return 'unspecified'

    return 'past' if past else 'future'


def remove_date_expressions(lowered: str) -> str:
    """Удаляет календарные даты перед извлечением города.

    Args:
        lowered: Нормализованный текст запроса.

    Returns:
        Текст без календарных дат.
    """
    cleaned = lowered

    for pattern in (
        ISO_DATE,
        NUMERIC_DATE,
        RU_WORD_DATE,
        EN_WORD_DATE,
    ):
        cleaned = pattern.sub(' ', cleaned)

    return re.sub(r'\s+', ' ', cleaned).strip()


def extract_city(lowered: str) -> str | None:
    """Извлекает предполагаемое название населённого пункта.

    Поддерживает запросы с географическими предлогами,
    составные названия и короткие запросы без предлогов.

    Args:
        lowered: Нормализованный текст запроса.

    Returns:
        Предполагаемое название или None.
    """
    cleaned = remove_date_expressions(lowered)

    # Вначале рассматриваем фрагменты после предлогов.
    # Временные предлоги и выражения отбрасываются.
    for match in CITY_PREPOSITION.finditer(cleaned):
        candidate = cleaned[match.end():]
        candidate = CITY_END.split(candidate, maxsplit=1)[0]
        candidate = CITY_WEATHER_WORDS.sub(' ', candidate)
        candidate = re.sub(r'\s+', ' ', candidate).strip(' ,')

        if (
            candidate
            and CITY_NAME.fullmatch(candidate)
            and not CITY_TIME_WORDS.fullmatch(candidate)
        ):
            return candidate.title()

    # Для коротких запросов без предлогов удаляем
    # погодные и временные выражения.
    candidate = CITY_WEATHER_WORDS.sub(' ', cleaned)

    for pattern in (
        CURRENT_PERIOD,
        WEEK_PERIOD,
        WEEKEND_PERIOD,
        FUTURE_INTENT,
        PAST_INTENT,
    ):
        candidate = pattern.sub(' ', candidate)

    for expression, _ in RELATIVE_DATES:
        candidate = re.sub(expression, ' ', candidate)

    candidate = re.sub(r'\s+', ' ', candidate).strip(' ,')

    if (
        candidate
        and CITY_NAME.fullmatch(candidate)
        and not CITY_TIME_WORDS.fullmatch(candidate)
        and not any(
            re.search(pattern, candidate)
            for patterns in METRICS.values()
            for pattern in patterns
        )
    ):
        return candidate.title()

    return None


def parse_query(text: str) -> WeatherQuery:
    """Разбирает пользовательский запрос на погоду.

    Args:
        text: Сообщение пользователя.

    Returns:
        Структурированный запрос WeatherQuery.

    Raises:
        ValueError: С кодом invalid_date для некорректной даты.
    """
    lowered = text.strip().casefold().replace('ё', 'е')
    language = 'ru' if re.search(r'[а-я]', lowered) else 'en'

    metrics = tuple(
        key
        for key, patterns in METRICS.items()
        if any(re.search(pattern, lowered) for pattern in patterns)
    )

    time_intent = detect_time_intent(lowered)

    period = 'day'
    relative_days = None
    weekday = None

    if CURRENT_PERIOD.search(lowered):
        period = 'now'
    else:
        for expression, offset in RELATIVE_DATES:
            if re.search(expression, lowered):
                relative_days = offset
                break

    if WEEK_PERIOD.search(lowered):
        period = 'week'
    elif WEEKEND_PERIOD.search(lowered):
        period = 'weekend'

    target_date, day, month = extract_calendar_date(lowered)

    explicit_date = (
        target_date is not None
        or day is not None
    )

    # Явная календарная дата имеет приоритет над периодами.
    if explicit_date:
        period = 'day'

    elif relative_days is None and period not in (
        'week',
        'weekend',
        'now',
    ):
        for word, day_number in WEEKDAYS.items():
            if re.search(
                r'(?<!\w)' + re.escape(word) + r'(?!\w)',
                lowered,
            ):
                weekday = day_number
                explicit_date = True
                break

    return WeatherQuery(
        city=extract_city(lowered),
        language=language,
        metrics=metrics,
        target_date=target_date,
        relative_days=relative_days,
        weekday=weekday,
        period=period,
        explicit_date=explicit_date,
        day=day,
        month=month,
        time_intent=time_intent,
    )


def resolve_date(
    query: WeatherQuery,
    local_today: date,
) -> date:
    """Определяет дату по локальному календарю города.

    Для календарной даты без года требует уточнения года,
    если пользователь явно не указал будущее намерение.

    При запросе будущей даты выбирает ближайшее допустимое
    календарное совпадение, включая високосные годы.

    Args:
        query: Разобранный пользовательский запрос.
        local_today: Текущая дата в часовом поясе города.

    Returns:
        Итоговая календарная дата.

    Raises:
        ValueError: С кодом year_required, если год неоднозначен.
    """
    if query.target_date:
        return query.target_date

    if query.day is not None and query.month is not None:
        if query.time_intent != 'future':
            raise ValueError('year_required')

        # Перебираем годы начиная с текущего, чтобы найти
        # ближайшую будущую дату, включая 29 февраля.
        # Девятилетний интервал учитывает исключения
        # из четырёхлетнего високосного цикла.
        for year in range(local_today.year, local_today.year + 9):
            try:
                target = date(year, query.month, query.day)
            except ValueError:
                continue

            if target >= local_today:
                return target

        raise ValueError('invalid_date')

    if query.relative_days is not None:
        return local_today + timedelta(days=query.relative_days)

    if query.weekday is not None:
        delta = (query.weekday - local_today.weekday()) % 7
        return local_today + timedelta(days=delta)

    return local_today

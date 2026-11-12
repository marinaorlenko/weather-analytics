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

from weather_analytics.bot.constants import (
    LEAP_REFERENCE_YEAR,
    WEEK_FORECAST_DAYS,
)
from weather_analytics.bot.parser_patterns import (
    CITY_END,
    CITY_NAME,
    CITY_PREPOSITION,
    CITY_TIME_WORDS,
    CITY_WEATHER_WORDS,
    CURRENT_PERIOD,
    EN_DAY_MONTH_DATE,
    EN_MONTHS,
    EN_WORD_DATE,
    FORECAST_DAYS,
    FUTURE_INTENT,
    ISO_DATE,
    METRICS,
    NEAREST_DAYS,
    NUMERIC_DATE,
    PAST_INTENT,
    RELATIVE_DATES,
    RU_MONTHS,
    RU_WORD_DATE,
    TIME_TYPO_REPLACEMENTS,
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
        period: Тип периода: now, day, week, weekend или days.
        explicit_date: Признак явного указания даты или дня недели.
        day: День месяца для даты без года.
        month: Месяц для даты без года.
        time_intent: Направленность запроса.
        forecast_days: Количество дней многодневного прогноза.
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
    forecast_days: int | None = None


def normalize_query(text: str) -> str:
    """Нормализует запрос и исправляет известные опечатки.

    Исправляет только явно заданные варианты временных
    выражений и месяцев, не изменяя названия городов.
    """
    normalized = text.strip().casefold().replace('ё', 'е')

    for pattern, replacement in TIME_TYPO_REPLACEMENTS:
        normalized = re.sub(
            pattern,
            replacement,
            normalized,
            flags=re.IGNORECASE,
        )

    return re.sub(r'\s+', ' ', normalized).strip()


def extract_calendar_date(
    lowered: str,
) -> tuple[date | None, int | None, int | None]:
    """Извлекает календарную дату без подстановки текущего года.

    Args:
        lowered: Нормализованный текст запроса.

    Returns:
        Полную дату либо отдельные день и месяц.

    Raises:
        ValueError: Если календарная дата некорректна.
    """
    iso = ISO_DATE.search(lowered)
    numeric = NUMERIC_DATE.search(lowered)
    words_ru = RU_WORD_DATE.search(lowered)
    words_en = EN_WORD_DATE.search(lowered)
    day_month_en = EN_DAY_MONTH_DATE.search(lowered)

    if not any((iso, numeric, words_ru, words_en, day_month_en)):
        return None, None, None

    try:
        if iso:
            year_str, month_str, day_str = iso.groups()

            return (
                date(
                    int(year_str),
                    int(month_str),
                    int(day_str),
                ),
                None,
                None,
            )

        if numeric:
            day_str, month_str, year_str = numeric.groups()
            day = int(day_str)
            month = int(month_str)

        elif words_ru:
            day_str, month_name, year_str = words_ru.groups()
            day = int(day_str)
            month = RU_MONTHS[month_name]

        elif words_en:
            month_name, day_str, year_str = words_en.groups()
            day = int(day_str)
            month = EN_MONTHS[month_name]

        elif day_month_en:
            day_str, month_name, year_str = day_month_en.groups()
            day = int(day_str)
            month = EN_MONTHS[month_name]

        else:
            return None, None, None

        year = int(year_str) if year_str else None

        if year is not None:
            return date(year, month, day), None, None

        # Проверяем день и месяц без выбора года запроса.
        # Опорный год високосный, поэтому 29 февраля допустимо.
        date(LEAP_REFERENCE_YEAR, month, day)

        return None, day, month

    except ValueError as exc:
        raise ValueError('invalid_date') from exc


def detect_time_intent(lowered: str) -> str:
    """Определяет прошлую или будущую направленность запроса."""
    past = bool(PAST_INTENT.search(lowered))
    future = bool(FUTURE_INTENT.search(lowered))

    if past == future:
        return 'unspecified'

    return 'past' if past else 'future'


def remove_date_expressions(lowered: str) -> str:
    """Удаляет календарные даты перед извлечением города."""
    cleaned = lowered

    for pattern in (
        ISO_DATE,
        NUMERIC_DATE,
        RU_WORD_DATE,
        EN_WORD_DATE,
        EN_DAY_MONTH_DATE,
    ):
        cleaned = pattern.sub(' ', cleaned)

    return re.sub(r'\s+', ' ', cleaned).strip()


def remove_time_expressions(lowered: str) -> str:
    """Удаляет временные выражения из кандидата в город.

    Удаление выполняется до поиска географических предлогов,
    чтобы конструкции «в ближайшие дни» не воспринимались
    как указание населённого пункта.
    """
    cleaned = remove_date_expressions(lowered)

    for pattern in (
        CURRENT_PERIOD,
        WEEK_PERIOD,
        WEEKEND_PERIOD,
        NEAREST_DAYS,
        FORECAST_DAYS,
        FUTURE_INTENT,
        PAST_INTENT,
    ):
        cleaned = pattern.sub(' ', cleaned)

    for expression, _ in RELATIVE_DATES:
        cleaned = re.sub(
            rf'(?<!\w)(?:{expression})(?!\w)',
            ' ',
            cleaned,
            flags=re.IGNORECASE,
        )

    for word in WEEKDAYS:
        cleaned = re.sub(
            rf'(?<!\w){re.escape(word)}(?!\w)',
            ' ',
            cleaned,
            flags=re.IGNORECASE,
        )

    return re.sub(r'\s+', ' ', cleaned).strip()


def clean_city_candidate(candidate: str) -> str | None:
    """Очищает и проверяет предполагаемое название города."""
    candidate = CITY_WEATHER_WORDS.sub(' ', candidate)

    # Убираем служебные слова только на краях фрагмента.
    # Внутренние части составных названий не изменяем.
    candidate = re.sub(
        r'^(?:(?:в|во|у|из|на|за|по|для|'
        r'in|for|at|on)\s+)+',
        '',
        candidate,
        flags=re.IGNORECASE,
    )

    candidate = re.sub(
        r'(?:\s+(?:в|во|у|из|на|за|по|для|'
        r'in|for|at|on))+$',
        '',
        candidate,
        flags=re.IGNORECASE,
    )

    candidate = re.sub(r'\s+', ' ', candidate).strip(' ,')

    if not candidate:
        return None

    if not CITY_NAME.fullmatch(candidate):
        return None

    if CITY_TIME_WORDS.fullmatch(candidate):
        return None

    if any(
        re.search(pattern, candidate, flags=re.IGNORECASE)
        for patterns in METRICS.values()
        for pattern in patterns
    ):
        return None

    return candidate.title()


def extract_city(lowered: str) -> str | None:
    """Извлекает предполагаемое название населённого пункта.

    Сначала удаляет даты и временные выражения, затем
    рассматривает фрагменты после географических предлогов.

    Если подходящего фрагмента нет, проверяет оставшийся
    текст целиком. Существование города здесь не проверяется.
    """
    cleaned = remove_time_expressions(lowered)

    # Убираем погодные слова до поиска предлогов.
    # Это позволяет обработать запросы с городом
    # как в начале, так и в конце сообщения.
    cleaned = CITY_WEATHER_WORDS.sub(' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    for match in CITY_PREPOSITION.finditer(cleaned):
        candidate = cleaned[match.end() :]
        candidate = CITY_END.split(candidate, maxsplit=1)[0]

        city = clean_city_candidate(candidate)

        if city is not None:
            return city

    # Запросы без предлога:
    # «Хошимин гроза», «London thunderstorm».
    return clean_city_candidate(cleaned)


def extract_forecast_days(lowered: str) -> int | None:
    """Определяет количество дней многодневного прогноза.

    Возвращает запрошенное число без ограничения семью днями.
    Проверка допустимого диапазона выполняется сервисом.
    """
    match = FORECAST_DAYS.search(lowered)

    if match:
        return int(match.group(1))

    if WEEK_PERIOD.search(lowered):
        return WEEK_FORECAST_DAYS

    if NEAREST_DAYS.search(lowered):
        return 3

    return None


def parse_query(text: str) -> WeatherQuery:
    """Разбирает пользовательский погодный запрос.

    Args:
        text: Сообщение пользователя.

    Returns:
        Структурированный запрос WeatherQuery.

    Raises:
        ValueError: С кодом invalid_date для некорректной даты.
    """
    lowered = normalize_query(text)
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
    forecast_days = None

    if CURRENT_PERIOD.search(lowered):
        period = 'now'

    else:
        for expression, offset in RELATIVE_DATES:
            if re.search(
                rf'(?<!\w)(?:{expression})(?!\w)',
                lowered,
                flags=re.IGNORECASE,
            ):
                relative_days = offset
                break

    # Определяем календарную дату до многодневного периода.
    # Явная дата имеет приоритет над остальными периодами.
    target_date, day, month = extract_calendar_date(lowered)

    explicit_date = target_date is not None or day is not None

    if explicit_date:
        period = 'day'

    elif period != 'now':
        if WEEKEND_PERIOD.search(lowered):
            period = 'weekend'

        else:
            forecast_days = extract_forecast_days(lowered)

            if WEEK_PERIOD.search(lowered):
                period = 'week'
            elif forecast_days is not None:
                period = 'days'

            elif relative_days is None:
                for word, day_number in WEEKDAYS.items():
                    if re.search(
                        rf'(?<!\w){re.escape(word)}(?!\w)',
                        lowered,
                    ):
                        weekday = day_number
                        explicit_date = True
                        break

    # Для запросов на конкретный день многодневный
    # период не применяется.
    if explicit_date or period in ('now', 'weekend'):
        forecast_days = None

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
        forecast_days=forecast_days,
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
        for year in range(
            local_today.year,
            local_today.year + 9,
        ):
            try:
                target = date(
                    year,
                    query.month,
                    query.day,
                )
            except ValueError:
                continue

            if target >= local_today:
                return target

        raise ValueError('invalid_date')

    if query.relative_days is not None:
        return local_today + timedelta(
            days=query.relative_days,
        )

    if query.weekday is not None:
        delta = (query.weekday - local_today.weekday()) % WEEK_FORECAST_DAYS

        return local_today + timedelta(days=delta)

    return local_today

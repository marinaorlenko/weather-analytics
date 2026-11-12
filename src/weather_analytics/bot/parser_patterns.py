"""Справочники и шаблоны для разбора погодных запросов Stormy.

Содержит русские и английские названия месяцев и дней недели,
шаблоны погодных показателей, календарных периодов,
временной направленности и выделения населённых пунктов.

Не зависит от Telegram, Open-Meteo и списка городов.
"""

import re

# Выражения, соответствующие погодным показателям.
METRICS: dict[str, tuple[str, ...]] = {
    'temperature': (r'температур|градус|тепл|холод|temperature|degrees|hot|cold',),
    'feels_like': (r'ощуща|по ощущениям|feels? like|apparent',),
    'wind': (r'ветер|ветра|ветром|порыв|wind|gust|windy',),
    'rain': (r'дожд|ливн|\brain\b|showers?',),
    'snow': (r'снег|снеж|снегопад|\bsnow\b|snowfall',),
    'thunderstorm': (r'гроз|гром|молни|thunder|lightning',),
    'precipitation': (r'осадк|precipitation',),
    'humidity': (r'влажност|humidity|humid',),
    'cloud': (r'облачност|облак|cloud|cloudy',),
    'pressure': (r'давлени|pressure',),
    'uv': (r'уф|ультрафиолет|uv[ -]?index|ultraviolet',),
}


# Номера месяцев для календарных дат.
RU_MONTHS: dict[str, int] = {
    'января': 1,
    'февраля': 2,
    'марта': 3,
    'апреля': 4,
    'мая': 5,
    'июня': 6,
    'июля': 7,
    'августа': 8,
    'сентября': 9,
    'октября': 10,
    'ноября': 11,
    'декабря': 12,
}

EN_MONTHS: dict[str, int] = {
    'january': 1,
    'february': 2,
    'march': 3,
    'april': 4,
    'may': 5,
    'june': 6,
    'july': 7,
    'august': 8,
    'september': 9,
    'october': 10,
    'november': 11,
    'december': 12,
}


# Номера дней недели: понедельник — 0, воскресенье — 6.
WEEKDAYS: dict[str, int] = {
    'понедельник': 0,
    'вторник': 1,
    'среду': 2,
    'среда': 2,
    'четверг': 3,
    'пятницу': 4,
    'пятница': 4,
    'субботу': 5,
    'суббота': 5,
    'воскресенье': 6,
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}


# Предлоги, после которых может следовать название города.
# Предлог «у» учитываем для запросов вида «снег у Дубая».
CITY_PREPOSITION = re.compile(
    r'\b(?:в|во|у|из|in|for|at)\s+',
    re.IGNORECASE,
)


# Слова и выражения, завершающие название города.
# Дефис внутри географического названия не является границей.
CITY_END = re.compile(
    r'(?<![\w-])(?:в|во|у|из|на|через|до|после|с|со|по|к|от|'
    r'сегодня|завтра|послезавтра|вчера|позавчера|сейчас|'
    r'утром|днем|днём|вечером|ночью|'
    r'ближайш\w*|следующ\w*|эт\w*|выходн\w*|'
    r'in|for|at|on|next|this|today|tomorrow|yesterday|now|'
    r'morning|afternoon|evening|tonight|weekend)\b|'
    r'[?!.,\d]',
    re.IGNORECASE,
)


# Погодные слова, которые не являются частью названия города.
CITY_WEATHER_WORDS = re.compile(
    r'\b(?:сейчас|погода|погоду|прогноз|температура|температуру|'
    r'дождь|осадки|ветер|влажность|снег|гроза|грозу|'
    r'грозы|weather|temperature|rain|wind|humidity|'
    r'thunderstorm|forecast|snow)\b',
    re.IGNORECASE,
)


# Временные выражения, которые не должны распознаваться
# как самостоятельные географические названия.
CITY_TIME_WORDS = re.compile(
    r'^(?:ближайш\w*|следующ\w*|эт\w*|недел\w*|'
    r'выходн\w*|момент|данный|день|дня|дней|days?|weeks?|'
    r'понедельник|вторник|среда|среду|четверг|'
    r'пятница|пятницу|суббота|субботу|воскресенье|'
    r'monday|tuesday|wednesday|thursday|friday|'
    r'saturday|sunday)$',
    re.IGNORECASE,
)


# Название может состоять из нескольких слов и содержать
# дефисы: New York, Великий Новгород, Ростов-на-Дону.
CITY_NAME = re.compile(
    r'[^\W\d_]+(?:[-\s][^\W\d_]+)*',
    re.UNICODE,
)


# Явные признаки запроса о будущей погоде.
FUTURE_INTENT = re.compile(
    r'\b(?:будет|будут|ожидается|ожидаются|'
    r'предстоящ\w*|будущ\w*|'
    r'will|going\s+to|upcoming|future)\b',
    re.IGNORECASE,
)


# Явные признаки запроса об исторической погоде.
PAST_INTENT = re.compile(
    r'\b(?:был|была|было|были|'
    r'прошл\w*|позапрошл\w*|'
    r'was|were|last|previous)\b',
    re.IGNORECASE,
)


# Относительные даты и текущая погода.
CURRENT_PERIOD = re.compile(
    r'сейчас|прямо сейчас|в данный момент|'
    r'\bnow\b|\bcurrent(?:ly)?\b|right now',
    re.IGNORECASE,
)

RELATIVE_DATES: tuple[tuple[str, int], ...] = (
    (r'послезавтра|day after tomorrow', 2),
    (r'завтра|tomorrow', 1),
    (r'сегодня|today', 0),
    (r'позавчера|day before yesterday', -2),
    (r'вчера|yesterday', -1),
)


# Периоды прогноза.
WEEK_PERIOD = re.compile(
    r'на (?:неделю|7 дней)|'
    r'(?:в\s+)?ближайш(?:ие|ую)\s+(?:7 дней|недел\w*)|'
    r'\b(?:7[- ]day|week(?:ly)?) forecast\b|'
    r'next (?:7 days|week)',
    re.IGNORECASE,
)

WEEKEND_PERIOD = re.compile(
    r'на выходных|в выходные|на этих выходных|'
    r'this weekend|next weekend',
    re.IGNORECASE,
)


# Явно указанное количество дней прогноза.
# Число не ограничиваем шаблоном: запрос на 10 дней
# должен быть распознан, чтобы сервис сообщил об ограничении.
FORECAST_DAYS = re.compile(
    r'(?<!\w)(?:на|за|в|for|next|following|over|'
    r'ближайшие|следующие|ближайших|следующих)?\s*'
    r'(\d{1,3})\s*'
    r'(?:день|дня|дней|days?)(?!\w)',
    re.IGNORECASE,
)


# «Ближайшие дни» без числа означают три дня.
NEAREST_DAYS = re.compile(
    r'\b(?:ближайш(?:ие|их)\s+дни|'
    r'в\s+ближайшие\s+дни|'
    r'next\s+few\s+days|'
    r'coming\s+days)\b',
    re.IGNORECASE,
)


# Форматы календарных дат.
ISO_DATE = re.compile(
    r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b',
)

NUMERIC_DATE = re.compile(
    r'\b(\d{1,2})[./](\d{1,2})(?:[./](\d{4}))?\b',
)

RU_WORD_DATE = re.compile(
    r'\b(\d{1,2})\s+(' + '|'.join(RU_MONTHS) + r')(?:\s+(\d{4}))?\b',
)

# Английская дата: November 11, 2025.
EN_WORD_DATE = re.compile(
    r'\b(' + '|'.join(EN_MONTHS) + r')\s+(\d{1,2})(?:,?\s+(\d{4}))?\b',
)

# Английская дата: 11 November 2025.
EN_DAY_MONTH_DATE = re.compile(
    r'\b(\d{1,2})\s+(' + '|'.join(EN_MONTHS) + r')(?:,?\s+(\d{4}))?\b',
)


# Известные опечатки во временных выражениях.
# Замены применяются к отдельным словам или фразам,
# чтобы не затрагивать названия населённых пунктов.
TIME_TYPO_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r'\bсегодн\s+я\b', 'сегодня'),
    (r'\bблтжайшие\b', 'ближайшие'),
    (r'\bнобяря\b', 'ноября'),
)

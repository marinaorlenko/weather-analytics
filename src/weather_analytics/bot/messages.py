"""Двуязычные сообщения и справочники локализации Telegram-бота Stormy.

Содержит пользовательские сообщения на русском и английском языках,
названия погодных показателей, месяцев и дней недели.

Не выполняет расчёты, форматирование погодных данных
или взаимодействие с Telegram API.
"""

MESSAGES = {
    'ru': {
        'welcome': (
            '🌪️ STORMY\n\n'
            'Привет! Я Сторми — твой погодный помощник.\n'
            'Расскажу о погоде в городах по всему миру.\n\n'
            'Hi! I’m Stormy, your personal weather assistant.\n'
            'Ask me about the weather anywhere in the world.\n\n'
            '🌍 Выбери язык / Choose your language:'
        ),
        'help': (
            '🌪️ STORMY — ПОМОЩЬ\n\n'
            'Напиши, какая погода тебя интересует и в каком городе.\n'
            'При желании укажи дату или конкретный показатель.\n\n'
            'Примеры:\n'
            '• Погода сегодня в Дубае\n'
            '• Температура завтра в Москве\n'
            '• Осадки в Лимасоле в пятницу\n'
            '• Прогноз на неделю в Лондоне\n'
            '• Погода в Риме 2025-10-01\n\n'
            '/start — приветствие\n'
            '/help — помощь\n'
            '/language — сменить язык'
        ),
        'no_city': (
            'Не удалось определить город. '
            'Например: «Температура завтра в Москве».'
        ),
        'not_found': (
            'Не нашёл город «{city}». '
            'Уточни название или укажи страну.'
        ),
        'suggestions': (
            'Не нашёл точного совпадения для «{city}». '
            'Возможно, ты ищешь один из этих городов:'
        ),
        'parse_city': (
            'Не смог уверенно выделить город из запроса. '
            'Попробуй: «Погода завтра в Москве».'
        ),
        'ambiguous': (
            'Нашлось несколько мест. Выбери нужное:'
        ),
        'error': (
            'Сейчас не удалось получить погодные данные. '
            'Попробуй позже.'
        ),
        'future_range': (
            'Прогноз доступен максимум на 16 дней вперёд.'
        ),
        'past_range': (
            'Для настолько ранней даты данные недоступны.'
        ),
        'mixed_range': (
            'Период пересекает прошлые и будущие дни; '
            'уточни дату.'
        ),
        'invalid_date': (
            'Не удалось распознать дату. '
            'Например: 2026-11-03.'
        ),
        'no_data': (
            'По этому показателю данных нет.'
        ),
        'lang': (
            '🌍 Выбери язык / Choose your language:'
        ),
        'language_set': (
            '🇷🇺 Русский язык выбран!'
        ),

        # Уточнение года для календарной даты без года.
        'year_required': (
            '📅 За какой год показать погоду '
            'в городе {city} на {date}?\n\n'
            'Выбери год или укажи другой.'
        ),
        'year_other': '✏️ Другой год',
        'year_input': (
            '✏️ Введи нужный год четырьмя цифрами, '
            'например 2022.'
        ),
        'year_invalid': (
            'Введи год четырьмя цифрами, например 2024.'
        ),
        'year_invalid_date': (
            'Такой даты не существует. '
            'Выбери другой год.'
        ),
        'year_selected': '📅 Выбран год: {year}',
        'year_expired': (
            'Этот запрос уже неактуален. '
            'Отправь новый вопрос о погоде.'
        ),

        'introduction': (
            '🌪️ Знакомься, я Stormy!\n\n'
            'Я помогу узнать погоду в городах по всему миру. '
            'Просто напиши вопрос обычными словами.\n\n'
            '🔎 ЧТО Я УМЕЮ\n\n'
            '🌡️ Температура и ощущаемая температура\n'
            '🌬️ Ветер и порывы\n'
            '🌧️ Дождь, снег, грозы и вероятность осадков\n'
            '💧 Влажность и давление\n'
            '☁️ Облачность и УФ-индекс\n'
            '📅 Прогноз до 16 дней\n'
            '🕰️ Погода за прошедшие даты\n\n'
            '💬 ПОПРОБУЙ СПРОСИТЬ\n\n'
            '• Какая погода завтра в Москве?\n'
            '• Ветер и температура в Дубае в пятницу\n'
            '• Прогноз на неделю в Лондоне\n'
            '• Погода в Париже 2025-10-01\n\n'
            '🌍 Чтобы сменить язык, отправь /language.\n\n'
            'Данные: Open-Meteo.'
        ),
    },

    'en': {
        'welcome': (
            '🌪️ STORMY\n\n'
            'Привет! Я Сторми — твой погодный помощник.\n'
            'Расскажу о погоде в городах по всему миру.\n\n'
            'Hi! I’m Stormy, your personal weather assistant.\n'
            'Ask me about the weather anywhere in the world.\n\n'
            '🌍 Выбери язык / Choose your language:'
        ),
        'help': (
            '🌪️ STORMY — HELP\n\n'
            'Tell me which city you are interested in.\n'
            'You can also specify a date or weather metric.\n\n'
            'Examples:\n'
            '• Weather in Dubai today\n'
            '• Temperature in London tomorrow\n'
            '• Rain in Paris on Friday\n'
            '• 7-day forecast for Tokyo\n'
            '• Weather in Rome on October 1, 2025\n\n'
            '/start — welcome\n'
            '/help — help\n'
            '/language — change language'
        ),
        'no_city': (
            'I could not identify the city. '
            'Try: “Temperature in London tomorrow”.'
        ),
        'not_found': (
            'I could not find «{city}». '
            'Please check the name or specify the country.'
        ),
        'suggestions': (
            'No exact match for «{city}». Did you mean:'
        ),
        'parse_city': (
            'I could not identify the city in your question. '
            'Try: “Weather tomorrow in London”.'
        ),
        'ambiguous': (
            'I found several places. Choose one:'
        ),
        'error': (
            'Weather data is temporarily unavailable. '
            'Please try again later.'
        ),
        'future_range': (
            'Forecasts are available up to 16 days ahead.'
        ),
        'past_range': (
            'Historical data is unavailable for such an early date.'
        ),
        'mixed_range': (
            'This period spans past and future days. '
            'Please specify a date.'
        ),
        'invalid_date': (
            'I could not understand the date. '
            'Try 2026-11-03.'
        ),
        'no_data': (
            'No data is available for this metric.'
        ),
        'lang': (
            '🌍 Choose your language / Выбери язык:'
        ),
        'language_set': (
            '🇬🇧 English selected!'
        ),

        # Уточнение года для календарной даты без года.
        'year_required': (
            '📅 Which year would you like for '
            '{date} in {city}?\n\n'
            'Choose a year or select another.'
        ),
        'year_other': '✏️ Another year',
        'year_input': (
            '✏️ Enter the year using four digits, '
            'for example 2022.'
        ),
        'year_invalid': (
            'Enter a four-digit year, for example 2024.'
        ),
        'year_invalid_date': (
            'That date does not exist. '
            'Choose another year.'
        ),
        'year_selected': '📅 Selected year: {year}',
        'year_expired': (
            'This request is no longer active. '
            'Please send a new weather question.'
        ),

        'introduction': (
            '🌪️ Meet Stormy!\n\n'
            'I’m your personal weather assistant. '
            'Ask me about the weather in cities around the world.\n\n'
            '🔎 WHAT I CAN DO\n\n'
            '🌡️ Temperature and feels-like temperature\n'
            '🌬️ Wind speed and gusts\n'
            '🌧️ Rain, snow, thunderstorms and precipitation probability\n'
            '💧 Humidity and atmospheric pressure\n'
            '☁️ Cloud cover and UV index\n'
            '📅 Forecasts up to 16 days ahead\n'
            '🕰️ Historical weather data\n\n'
            '💬 TRY ASKING\n\n'
            '• What’s the weather in Dubai tomorrow?\n'
            '• Wind and temperature in London on Friday\n'
            '• 7-day forecast for Paris\n'
            '• Weather in Rome on October 1, 2025\n\n'
            '🌍 To change your language, send /language.\n\n'
            'Powered by Open-Meteo.'
        ),
    },
}


# Локализованные названия и единицы измерения погодных показателей.
LABELS = {
    'temperature': (
        '🌡️ Температура',
        '🌡️ Temperature',
        '°C',
    ),
    'feels_like': (
        '🤗 Ощущается',
        '🤗 Feels like',
        '°C',
    ),
    'wind': (
        '🌬️ Ветер',
        '🌬️ Wind',
        'км/ч',
    ),
    'rain': (
        '🌧️ Дождь',
        '🌧️ Rain',
        'мм',
    ),
    'snow': (
        '❄️ Снег',
        '❄️ Snow',
        'см',
    ),
    'thunderstorm': (
        '⚡ Гроза',
        '⚡ Thunderstorm',
        '',
    ),
    'precipitation': (
        '🌦️ Осадки',
        '🌦️ Precipitation',
        'мм',
    ),
    'humidity': (
        '💧 Влажность',
        '💧 Humidity',
        '%',
    ),
    'cloud': (
        '☁️ Облачность',
        '☁️ Cloud cover',
        '%',
    ),
    'pressure': (
        '🧭 Давление',
        '🧭 Pressure',
        'гПа',
    ),
    'uv': (
        '☀️ УФ-индекс',
        '☀️ UV index',
        '',
    ),
}


# Названия месяцев в родительном падеже для русских дат.
MONTHS_RU = (
    '',
    'января',
    'февраля',
    'марта',
    'апреля',
    'мая',
    'июня',
    'июля',
    'августа',
    'сентября',
    'октября',
    'ноября',
    'декабря',
)


WEEKDAYS_RU = (
    'понедельник',
    'вторник',
    'среда',
    'четверг',
    'пятница',
    'суббота',
    'воскресенье',
)


WEEKDAYS_EN = (
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
)


MONTHS_EN = (
    '',
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
)

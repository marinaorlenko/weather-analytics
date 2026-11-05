# """Обработчики Telegram для двуязычного погодного бота Stormy.

# Управляет выбором языка, поиском населённых пунктов,
# получением погоды и уточнением года для неоднозначных дат.

# Погодные расчёты и форматирование ответов выполняются
# в отдельных модулях.
# """

# import asyncio
# import logging
# import re
# from dataclasses import replace
# from datetime import date, datetime
# from pathlib import Path
# from typing import Any
# from zoneinfo import ZoneInfo

# import httpx
# from telegram import (
#     InlineKeyboardButton,
#     InlineKeyboardMarkup,
#     LinkPreviewOptions,
#     Update,
# )
# from telegram.ext import (
#     Application,
#     CallbackQueryHandler,
#     CommandHandler,
#     ContextTypes,
#     MessageHandler,
#     PicklePersistence,
#     filters,
# )

# from weather_analytics.api import OpenMeteoClient
# from weather_analytics.bot.city_search import CitySearchService
# from weather_analytics.bot.constants import (
#     CITY_SELECTION_LIMIT,
#     MAX_MESSAGE_LENGTH,
#     YEAR_SELECTION_COUNT,
# )
# from weather_analytics.bot.messages import MESSAGES
# from weather_analytics.bot.parser import WeatherQuery, parse_query
# from weather_analytics.bot.service import WeatherService
# from weather_analytics.bot.weather_formatter import format_weather
# from weather_analytics.config import get_settings


# LOGGER = logging.getLogger(__name__)


# def preferred_language(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> str:
#     """Возвращает сохранённый язык или язык интерфейса Telegram."""
#     saved = context.user_data.get('language')

#     if saved in MESSAGES:
#         return saved

#     telegram_language = (
#         update.effective_user.language_code or ''
#     )

#     return (
#         'ru'
#         if telegram_language.startswith('ru')
#         else 'en'
#     )


# def language_keyboard() -> InlineKeyboardMarkup:
#     """Создаёт кнопки выбора языка."""
#     return InlineKeyboardMarkup([
#         [
#             InlineKeyboardButton(
#                 '🇷🇺 Русский',
#                 callback_data='lang:ru',
#             ),
#             InlineKeyboardButton(
#                 '🇬🇧 English',
#                 callback_data='lang:en',
#             ),
#         ],
#     ])


# def city_keyboard(
#     cities: list[dict[str, Any]],
# ) -> InlineKeyboardMarkup:
#     """Формирует кнопки выбора найденных населённых пунктов."""
#     buttons = []

#     for index, city in enumerate(cities[:CITY_SELECTION_LIMIT]):
#         # Регион и страна позволяют различать одноимённые города.
#         label = ', '.join(
#             str(value)
#             for value in (
#                 city.get('name'),
#                 city.get('admin1'),
#                 city.get('country'),
#             )
#             if value
#         )

#         buttons.append([
#             InlineKeyboardButton(
#                 label,
#                 callback_data=f'city:{index}',
#             ),
#         ])

#     return InlineKeyboardMarkup(buttons)


# def year_keyboard(
#     city: dict[str, Any],
#     language: str,
# ) -> InlineKeyboardMarkup:
#     """Создаёт кнопки выбора года с учётом времени города."""
#     timezone = city.get('timezone') or 'UTC'
#     current_year = datetime.now(ZoneInfo(timezone)).year

#     years = range(
#         current_year,
#         current_year - YEAR_SELECTION_COUNT,
#         -1,
#     )

#     buttons = [
#         [
#             InlineKeyboardButton(
#                 str(year),
#                 callback_data=f'year:{year}',
#             ),
#         ]
#         for year in years
#     ]

#     buttons.append([
#         InlineKeyboardButton(
#             MESSAGES[language]['year_other'],
#             callback_data='year:other',
#         ),
#     ])

#     return InlineKeyboardMarkup(buttons)


# def clear_pending_year(
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> None:
#     """Удаляет временное состояние уточнения года."""
#     for key in (
#         'pending_year_city',
#         'pending_year_query',
#         'pending_year_language',
#         'pending_year_message_id',
#         'awaiting_year_input',
#     ):
#         context.user_data.pop(key, None)


# def clear_pending_city(
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> None:
#     """Удаляет временное состояние выбора города."""
#     for key in (
#         'pending_query',
#         'pending_cities',
#         'pending_language',
#         'pending_city_message_id',
#     ):
#         context.user_data.pop(key, None)


# def fetch_locations(
#     city: str,
#     language: str,
# ) -> tuple[list[dict[str, Any]], bool]:
#     """Ищет города и сообщает, использовались ли предложения."""
#     with OpenMeteoClient() as client:
#         return CitySearchService(client).search_cities(
#             city,
#             language,
#         )


# def fetch_weather(
#     city: dict[str, Any],
#     query: WeatherQuery,
# ) -> dict[str, Any]:
#     """Получает погодные данные для выбранного города."""
#     with OpenMeteoClient() as client:
#         return WeatherService(client).get_weather(
#             city,
#             query,
#         )


# def split_weather_message(
#     response: str,
# ) -> list[str]:
#     """Разделяет длинный HTML-ответ по границам строк.

#     Не разрезает HTML-теги и ссылки внутри строк.
#     Возвращает готовые части для отправки в Telegram.
#     """
#     if len(response) <= MAX_MESSAGE_LENGTH:
#         return [response]

#     parts = []
#     current_lines = []
#     current_length = 0

#     for line in response.split('\n'):
#         # Отдельные строки форматтера должны быть короткими.
#         # Не разрезаем HTML-разметку посередине строки.
#         if len(line) > MAX_MESSAGE_LENGTH:
#             raise ValueError('message_line_too_long')

#         additional_length = len(line) + (
#             1 if current_lines else 0
#         )

#         if (
#             current_lines
#             and current_length + additional_length
#             > MAX_MESSAGE_LENGTH
#         ):
#             parts.append('\n'.join(current_lines))
#             current_lines = [line]
#             current_length = len(line)
#         else:
#             current_lines.append(line)
#             current_length += additional_length

#     if current_lines:
#         parts.append('\n'.join(current_lines))

#     return parts


# async def send_weather_message(
#     update: Update,
#     response: str,
# ) -> None:
#     """Отправляет погодный ответ без повреждения HTML-разметки."""
#     for part in split_weather_message(response):
#         await update.effective_message.reply_text(
#             part,
#             parse_mode='HTML',
#             link_preview_options=LinkPreviewOptions(
#                 is_disabled=True,
#             ),
#         )


# async def start(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> None:
#     """Приветствует пользователя и предлагает выбрать язык."""
#     clear_pending_city(context)
#     clear_pending_year(context)

#     await update.message.reply_text(
#         MESSAGES['ru']['welcome'],
#         reply_markup=language_keyboard(),
#     )


# async def language_command(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> None:
#     """Предлагает изменить язык интерфейса."""
#     language = preferred_language(update, context)

#     await update.message.reply_text(
#         MESSAGES[language]['lang'],
#         reply_markup=language_keyboard(),
#     )


# async def language_callback(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> None:
#     """Сохраняет язык и показывает возможности Stormy."""
#     callback = update.callback_query
#     await callback.answer()

#     language = callback.data.split(':', maxsplit=1)[1]
#     context.user_data['language'] = language

#     await callback.edit_message_text(
#         MESSAGES[language]['language_set'],
#     )

#     await callback.message.reply_text(
#         MESSAGES[language]['introduction'],
#     )


# async def help_command(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> None:
#     """Показывает справку на выбранном языке."""
#     language = preferred_language(update, context)

#     await update.message.reply_text(
#         MESSAGES[language]['help'],
#     )


# async def request_year(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
#     city: dict[str, Any],
#     query: WeatherQuery,
#     language: str,
# ) -> None:
#     """Запрашивает год и сохраняет исходный погодный запрос."""
#     clear_pending_year(context)

#     context.user_data['pending_year_city'] = city
#     context.user_data['pending_year_query'] = query
#     context.user_data['pending_year_language'] = language
#     context.user_data['awaiting_year_input'] = False

#     requested_date = f'{query.day:02d}.{query.month:02d}'

#     message = MESSAGES[language]['year_required'].format(
#         city=city.get('name', ''),
#         date=requested_date,
#     )

#     sent_message = await update.effective_message.reply_text(
#         message,
#         reply_markup=year_keyboard(city, language),
#     )

#     context.user_data['pending_year_message_id'] = (
#         sent_message.message_id
#     )


# async def respond_weather(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
#     city: dict[str, Any],
#     query: WeatherQuery,
#     language: str,
# ) -> None:
#     """Получает погоду и отправляет ответ либо запрашивает год."""
#     try:
#         result = await asyncio.to_thread(
#             fetch_weather,
#             city,
#             query,
#         )

#         response = format_weather(
#             city,
#             query,
#             result,
#             language,
#         )

#         await send_weather_message(update, response)

#         clear_pending_year(context)
#         clear_pending_city(context)

#     except ValueError as exc:
#         code = str(exc)

#         if code == 'year_required':
#             await request_year(
#                 update,
#                 context,
#                 city,
#                 query,
#                 language,
#             )
#             return

#         if code not in MESSAGES[language]:
#             LOGGER.exception(
#                 'Ошибка обработки погодных данных: %s',
#                 exc,
#             )

#         await update.effective_message.reply_text(
#             MESSAGES[language].get(
#                 code,
#                 MESSAGES[language]['error'],
#             ),
#         )

#     except (
#         httpx.HTTPError,
#         KeyError,
#         TypeError,
#         IndexError,
#     ) as exc:
#         LOGGER.exception(
#             'Ошибка получения погоды: %s',
#             exc,
#         )

#         await update.effective_message.reply_text(
#             MESSAGES[language]['error'],
#         )


# async def complete_year_selection(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
#     year: int,
# ) -> None:
#     """Продолжает сохранённый запрос после выбора года.

#     Проверяет календарную дату и передаёт запрос погодному
#     сервису без повторного поиска населённого пункта.
#     """
#     city = context.user_data.get('pending_year_city')
#     query = context.user_data.get('pending_year_query')

#     language = context.user_data.get(
#         'pending_year_language',
#         preferred_language(update, context),
#     )

#     if not city or not query:
#         await update.effective_message.reply_text(
#             MESSAGES[language]['year_expired'],
#         )
#         clear_pending_year(context)
#         return

#     try:
#         # Проверяем календарную дату, включая високосные годы.
#         selected_date = date(
#             year,
#             query.month,
#             query.day,
#         )

#     except ValueError:
#         # Сохраняем ID нового сообщения, чтобы повторный
#         # выбор года не считался устаревшим.
#         context.user_data['awaiting_year_input'] = False

#         sent_message = await update.effective_message.reply_text(
#             MESSAGES[language]['year_invalid_date'],
#             reply_markup=year_keyboard(city, language),
#         )

#         context.user_data['pending_year_message_id'] = (
#             sent_message.message_id
#         )
#         return

#     # WeatherQuery — неизменяемый dataclass.
#     # Создаём копию с выбранной календарной датой.
#     resolved_query = replace(
#         query,
#         target_date=selected_date,
#         day=None,
#         month=None,
#     )

#     clear_pending_year(context)

#     await respond_weather(
#         update,
#         context,
#         city,
#         resolved_query,
#         language,
#     )


# async def handle_year_input(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> bool:
#     """Обрабатывает ручной ввод года.

#     Возвращает True, если сообщение обработано как ввод года,
#     иначе False для дальнейшего разбора погодного запроса.
#     """
#     if not context.user_data.get('awaiting_year_input'):
#         return False

#     text = update.message.text.strip()

#     language = context.user_data.get(
#         'pending_year_language',
#         preferred_language(update, context),
#     )

#     # Новый погодный запрос отменяет ожидание года.
#     if not re.fullmatch(r'\d{1,4}', text):
#         clear_pending_year(context)
#         return False

#     if not re.fullmatch(r'\d{4}', text):
#         await update.message.reply_text(
#             MESSAGES[language]['year_invalid'],
#         )
#         return True

#     await complete_year_selection(
#         update,
#         context,
#         int(text),
#     )

#     return True


# async def handle_text(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> None:
#     """Разбирает текст, ищет город и запрашивает погоду."""
#     if await handle_year_input(update, context):
#         return

#     clear_pending_year(context)
#     clear_pending_city(context)

#     language = preferred_language(update, context)

#     try:
#         query = parse_query(update.message.text)

#     except ValueError:
#         await update.message.reply_text(
#             MESSAGES[language]['invalid_date'],
#         )
#         return

#     # Язык, выбранный пользователем, имеет приоритет
#     # над языком, автоматически определённым парсером.
#     saved_language = context.user_data.get('language')

#     language = (
#         saved_language
#         if saved_language in MESSAGES
#         else query.language
#         if query.language in MESSAGES
#         else language
#     )

#     if not query.city:
#         await update.message.reply_text(
#             MESSAGES[language]['parse_city'],
#         )
#         return

#     try:
#         # Единый поиск: точные совпадения и, при необходимости,
#         # варианты с опечатками. Выполняется вне event loop.
#         cities, suggested = await asyncio.to_thread(
#             fetch_locations,
#             query.city,
#             language,
#         )

#     except (httpx.HTTPError, ValueError) as exc:
#         LOGGER.exception(
#             'Ошибка геокодирования: %s',
#             exc,
#         )

#         await update.message.reply_text(
#             MESSAGES[language]['error'],
#         )
#         return

#     if not cities:
#         await update.message.reply_text(
#             MESSAGES[language]['not_found'].format(
#                 city=query.city,
#             ),
#         )
#         return

#     # Однозначное точное совпадение не требует кнопок.
#     if len(cities) == 1 and not suggested:
#         await respond_weather(
#             update,
#             context,
#             cities[0],
#             query,
#             language,
#         )
#         return

#     # Сохраняем исходный запрос и список городов,
#     # чтобы выбор кнопки не запускал геокодирование повторно.
#     context.user_data['pending_query'] = query
#     context.user_data['pending_cities'] = (
#         cities[:CITY_SELECTION_LIMIT]
#     )
#     context.user_data['pending_language'] = language

#     message = (
#         MESSAGES[language]['suggestions'].format(
#             city=query.city,
#         )
#         if suggested
#         else MESSAGES[language]['ambiguous']
#     )

#     sent_message = await update.message.reply_text(
#         message,
#         reply_markup=city_keyboard(cities),
#     )

#     context.user_data['pending_city_message_id'] = (
#         sent_message.message_id
#     )


# async def city_callback(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> None:
#     """Продолжает запрос после выбора населённого пункта."""
#     callback = update.callback_query
#     await callback.answer()

#     cities = context.user_data.get('pending_cities') or []
#     query = context.user_data.get('pending_query')

#     language = context.user_data.get(
#         'pending_language',
#         preferred_language(update, context),
#     )

#     message_id = context.user_data.get(
#         'pending_city_message_id',
#     )

#     # Старые кнопки не должны использовать данные
#     # нового или уже завершённого запроса.
#     if (
#         message_id != callback.message.message_id
#         or not query
#     ):
#         await callback.edit_message_text(
#             MESSAGES[language]['year_expired'],
#         )
#         return

#     index = int(
#         callback.data.split(':', maxsplit=1)[1]
#     )

#     if not 0 <= index < len(cities):
#         await callback.edit_message_text(
#             MESSAGES[language]['no_city'],
#         )
#         clear_pending_city(context)
#         return

#     city = cities[index]

#     await callback.edit_message_text(
#         f'📍 {city.get("name", "")}, '
#         f'{city.get("country", "")}',
#     )

#     clear_pending_city(context)

#     await respond_weather(
#         update,
#         context,
#         city,
#         query,
#         language,
#     )


# async def year_callback(
#     update: Update,
#     context: ContextTypes.DEFAULT_TYPE,
# ) -> None:
#     """Обрабатывает выбор года через кнопки Telegram."""
#     callback = update.callback_query
#     await callback.answer()

#     language = context.user_data.get(
#         'pending_year_language',
#         preferred_language(update, context),
#     )

#     city = context.user_data.get('pending_year_city')
#     query = context.user_data.get('pending_year_query')

#     message_id = context.user_data.get(
#         'pending_year_message_id',
#     )

#     if (
#         not city
#         or not query
#         or message_id != callback.message.message_id
#     ):
#         await callback.edit_message_text(
#             MESSAGES[language]['year_expired'],
#         )
#         return

#     value = callback.data.split(':', maxsplit=1)[1]

#     if value == 'other':
#         context.user_data['awaiting_year_input'] = True

#         await callback.edit_message_text(
#             MESSAGES[language]['year_input'],
#         )
#         return

#     year = int(value)

#     await callback.edit_message_text(
#         MESSAGES[language]['year_selected'].format(
#             year=year,
#         ),
#     )

#     await complete_year_selection(
#         update,
#         context,
#         year,
#     )


# def main() -> None:
#     """Запускает Telegram-бота через long polling."""
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s | %(levelname)s | %(message)s',
#     )

#     token = (
#         get_settings()
#         .telegram_bot_token
#         .get_secret_value()
#     )

#     persistence_path = Path('data/stormy_users.pkl')

#     persistence_path.parent.mkdir(
#         parents=True,
#         exist_ok=True,
#     )

#     application = (
#         Application.builder()
#         .token(token)
#         .persistence(
#             PicklePersistence(
#                 filepath=persistence_path,
#             ),
#         )
#         .build()
#     )

#     application.add_handler(
#         CommandHandler('start', start),
#     )

#     application.add_handler(
#         CommandHandler('help', help_command),
#     )

#     application.add_handler(
#         CommandHandler('language', language_command),
#     )

#     application.add_handler(
#         CallbackQueryHandler(
#             language_callback,
#             pattern=r'^lang:(ru|en)$',
#         ),
#     )

#     application.add_handler(
#         CallbackQueryHandler(
#             city_callback,
#             pattern=r'^city:\d+$',
#         ),
#     )

#     application.add_handler(
#         CallbackQueryHandler(
#             year_callback,
#             pattern=r'^year:(?:\d{4}|other)$',
#         ),
#     )

#     application.add_handler(
#         MessageHandler(
#             filters.TEXT & ~filters.COMMAND,
#             handle_text,
#         ),
#     )

#     application.run_polling()


# if __name__ == '__main__':
#     main()


"""Обработчики Telegram для двуязычного погодного бота Stormy.

Управляет выбором языка, поиском населённых пунктов,
получением погоды и уточнением года для неоднозначных дат.

Погодные расчёты и форматирование ответов выполняются
в отдельных модулях.
"""

import asyncio
import logging
import re
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)

from weather_analytics.api import OpenMeteoClient
from weather_analytics.bot.city_search import CitySearchService
from weather_analytics.bot.constants import (
    CITY_SELECTION_LIMIT,
    MAX_MESSAGE_LENGTH,
    YEAR_SELECTION_COUNT,
)
from weather_analytics.bot.messages import MESSAGES
from weather_analytics.bot.parser import WeatherQuery, parse_query
from weather_analytics.bot.service import WeatherService
from weather_analytics.bot.weather_formatter import format_weather
from weather_analytics.config import get_settings

LOGGER = logging.getLogger(__name__)


def user_state(
    context: ContextTypes.DEFAULT_TYPE,
) -> dict[str, Any] | None:
    """Возвращает доступное состояние пользователя."""
    return context.user_data


def preferred_language(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    """Возвращает сохранённый язык или язык интерфейса Telegram."""
    state = user_state(context)
    saved = state.get('language') if state is not None else None

    if isinstance(saved, str) and saved in MESSAGES:
        return saved

    user = update.effective_user
    telegram_language = user.language_code if user else ''

    return 'ru' if (telegram_language or '').startswith('ru') else 'en'


def stored_language(
    state: dict[str, Any],
    key: str,
    fallback: str,
) -> str:
    """Получает корректный язык из сохранённого состояния."""
    value = state.get(key)
    return value if isinstance(value, str) and value in MESSAGES else fallback


def get_message(update: Update) -> Message | None:
    """Возвращает доступное сообщение для ответа."""
    return update.effective_message


async def reply(
    update: Update,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """Отправляет ответ, если исходное сообщение доступно."""
    message = get_message(update)

    if message is None:
        LOGGER.warning('Не удалось ответить: сообщение недоступно')
        return None

    return await message.reply_text(
        text,
        reply_markup=reply_markup,
    )


def get_callback(update: Update) -> CallbackQuery | None:
    """Возвращает callback с текстовыми данными."""
    callback = update.callback_query

    if callback is None or not isinstance(callback.data, str):
        return None

    return callback


def callback_message_id(callback: CallbackQuery) -> int | None:
    """Возвращает ID сообщения, связанного с кнопкой."""
    message = callback.message
    return message.message_id if message is not None else None


def language_keyboard() -> InlineKeyboardMarkup:
    """Создаёт кнопки выбора языка."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                '🇷🇺 Русский',
                callback_data='lang:ru',
            ),
            InlineKeyboardButton(
                '🇬🇧 English',
                callback_data='lang:en',
            ),
        ],
    ])


def city_keyboard(
    cities: list[dict[str, Any]],
) -> InlineKeyboardMarkup:
    """Формирует кнопки выбора найденных населённых пунктов."""
    buttons = []

    for index, city in enumerate(cities[:CITY_SELECTION_LIMIT]):
        # Регион и страна различают одноимённые города.
        label = ', '.join(
            str(value)
            for value in (
                city.get('name'),
                city.get('admin1'),
                city.get('country'),
            )
            if value
        )

        buttons.append([
            InlineKeyboardButton(
                label,
                callback_data=f'city:{index}',
            ),
        ])

    return InlineKeyboardMarkup(buttons)


def year_keyboard(
    city: dict[str, Any],
    language: str,
) -> InlineKeyboardMarkup:
    """Создаёт кнопки выбора года с учётом времени города."""
    timezone = city.get('timezone') or 'UTC'

    try:
        current_year = datetime.now(ZoneInfo(str(timezone))).year
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        current_year = datetime.now(ZoneInfo('UTC')).year

    years = range(
        current_year,
        current_year - YEAR_SELECTION_COUNT,
        -1,
    )

    buttons = [
        [
            InlineKeyboardButton(
                str(year),
                callback_data=f'year:{year}',
            ),
        ]
        for year in years
    ]

    buttons.append([
        InlineKeyboardButton(
            MESSAGES[language]['year_other'],
            callback_data='year:other',
        ),
    ])

    return InlineKeyboardMarkup(buttons)


def clear_pending_year(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Удаляет временное состояние уточнения года."""
    state = user_state(context)

    if state is None:
        return

    for key in (
        'pending_year_city',
        'pending_year_query',
        'pending_year_language',
        'pending_year_message_id',
        'awaiting_year_input',
    ):
        state.pop(key, None)


def clear_pending_city(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Удаляет временное состояние выбора города."""
    state = user_state(context)

    if state is None:
        return

    for key in (
        'pending_query',
        'pending_cities',
        'pending_language',
        'pending_city_message_id',
    ):
        state.pop(key, None)


def fetch_locations(
    city: str,
    language: str,
) -> tuple[list[dict[str, Any]], bool]:
    """Ищет города и сообщает, использовались ли предложения."""
    with OpenMeteoClient() as client:
        return CitySearchService(client).search_cities(
            city,
            language,
        )


def fetch_weather(
    city: dict[str, Any],
    query: WeatherQuery,
) -> dict[str, Any]:
    """Получает погодные данные для выбранного города."""
    with OpenMeteoClient() as client:
        return WeatherService(client).get_weather(
            city,
            query,
        )


def split_weather_message(response: str) -> list[str]:
    """Разделяет длинный HTML-ответ по границам строк.

    Не разрезает HTML-теги и ссылки внутри строк.
    """
    if len(response) <= MAX_MESSAGE_LENGTH:
        return [response]

    parts: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    for line in response.split('\n'):
        if len(line) > MAX_MESSAGE_LENGTH:
            raise ValueError('message_line_too_long')

        additional_length = len(line) + (1 if current_lines else 0)

        if (
            current_lines
            and current_length + additional_length > MAX_MESSAGE_LENGTH
        ):
            parts.append('\n'.join(current_lines))
            current_lines = [line]
            current_length = len(line)
        else:
            current_lines.append(line)
            current_length += additional_length

    if current_lines:
        parts.append('\n'.join(current_lines))

    return parts


async def send_weather_message(
    update: Update,
    response: str,
) -> None:
    """Отправляет погодный ответ без повреждения HTML-разметки."""
    message = get_message(update)

    if message is None:
        LOGGER.warning('Погодный ответ не отправлен: нет сообщения')
        return

    for part in split_weather_message(response):
        await message.reply_text(
            part,
            parse_mode='HTML',
            link_preview_options=LinkPreviewOptions(
                is_disabled=True,
            ),
        )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Приветствует пользователя и предлагает выбрать язык."""
    clear_pending_city(context)
    clear_pending_year(context)

    await reply(
        update,
        MESSAGES['ru']['welcome'],
        reply_markup=language_keyboard(),
    )


async def language_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Предлагает изменить язык интерфейса."""
    language = preferred_language(update, context)

    await reply(
        update,
        MESSAGES[language]['lang'],
        reply_markup=language_keyboard(),
    )


async def language_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Сохраняет язык и показывает возможности Stormy."""
    callback = get_callback(update)

    if callback is None:
        return

    await callback.answer()

    language = callback.data.split(':', maxsplit=1)[1]

    if language not in MESSAGES:
        return

    state = user_state(context)

    if state is not None:
        state['language'] = language

    await callback.edit_message_text(
        MESSAGES[language]['language_set'],
    )

    await reply(
        update,
        MESSAGES[language]['introduction'],
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Показывает справку на выбранном языке."""
    language = preferred_language(update, context)

    await reply(
        update,
        MESSAGES[language]['help'],
    )


async def request_year(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    city: dict[str, Any],
    query: WeatherQuery,
    language: str,
) -> None:
    """Запрашивает год и сохраняет исходный погодный запрос."""
    state = user_state(context)

    if state is None:
        LOGGER.warning('Невозможно сохранить запрос уточнения года')
        return

    clear_pending_year(context)

    state['pending_year_city'] = city
    state['pending_year_query'] = query
    state['pending_year_language'] = language
    state['awaiting_year_input'] = False

    requested_date = f'{query.day:02d}.{query.month:02d}'

    message = MESSAGES[language]['year_required'].format(
        city=city.get('name', ''),
        date=requested_date,
    )

    sent_message = await reply(
        update,
        message,
        reply_markup=year_keyboard(city, language),
    )

    if sent_message is not None:
        state['pending_year_message_id'] = sent_message.message_id
    else:
        clear_pending_year(context)


async def respond_weather(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    city: dict[str, Any],
    query: WeatherQuery,
    language: str,
) -> None:
    """Получает погоду и отправляет ответ либо запрашивает год."""
    try:
        result = await asyncio.to_thread(
            fetch_weather,
            city,
            query,
        )

        response = format_weather(
            city,
            query,
            result,
            language,
        )

        await send_weather_message(update, response)

        clear_pending_year(context)
        clear_pending_city(context)

    except ValueError as exc:
        code = str(exc)

        if code == 'year_required':
            await request_year(
                update,
                context,
                city,
                query,
                language,
            )
            return

        if code not in MESSAGES[language]:
            LOGGER.exception(
                'Ошибка обработки погодных данных: %s',
                exc,
            )

        await reply(
            update,
            MESSAGES[language].get(
                code,
                MESSAGES[language]['error'],
            ),
        )

    except (
        httpx.HTTPError,
        KeyError,
        TypeError,
        IndexError,
    ) as exc:
        LOGGER.exception(
            'Ошибка получения погоды: %s',
            exc,
        )

        await reply(
            update,
            MESSAGES[language]['error'],
        )


async def complete_year_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    year: int,
) -> None:
    """Продолжает сохранённый запрос после выбора года."""
    state = user_state(context)

    if state is None:
        return

    city = state.get('pending_year_city')
    query = state.get('pending_year_query')

    language = stored_language(
        state,
        'pending_year_language',
        preferred_language(update, context),
    )

    if not isinstance(city, dict) or not isinstance(query, WeatherQuery):
        await reply(
            update,
            MESSAGES[language]['year_expired'],
        )
        clear_pending_year(context)
        return

    if query.month is None or query.day is None:
        await reply(
            update,
            MESSAGES[language]['year_expired'],
        )
        clear_pending_year(context)
        return

    try:
        # Проверяем дату с учётом високосных лет.
        selected_date = date(year, query.month, query.day)

    except ValueError:
        state['awaiting_year_input'] = False

        sent_message = await reply(
            update,
            MESSAGES[language]['year_invalid_date'],
            reply_markup=year_keyboard(city, language),
        )

        if sent_message is not None:
            state['pending_year_message_id'] = sent_message.message_id

        return

    # WeatherQuery — неизменяемый dataclass.
    resolved_query = replace(
        query,
        target_date=selected_date,
        day=None,
        month=None,
    )

    clear_pending_year(context)

    await respond_weather(
        update,
        context,
        city,
        resolved_query,
        language,
    )


async def handle_year_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """Обрабатывает ручной ввод года.

    Возвращает True, если сообщение обработано как ввод года.
    """
    state = user_state(context)

    if state is None or not state.get('awaiting_year_input'):
        return False

    message = update.message

    if message is None or not isinstance(message.text, str):
        return False

    text = message.text.strip()

    language = stored_language(
        state,
        'pending_year_language',
        preferred_language(update, context),
    )

    # Новый погодный запрос отменяет ожидание года.
    if not re.fullmatch(r'\d{1,4}', text):
        clear_pending_year(context)
        return False

    if not re.fullmatch(r'\d{4}', text):
        await reply(
            update,
            MESSAGES[language]['year_invalid'],
        )
        return True

    await complete_year_selection(
        update,
        context,
        int(text),
    )

    return True


async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Разбирает текст, ищет город и запрашивает погоду."""
    message = update.message

    if message is None or not isinstance(message.text, str):
        return

    if await handle_year_input(update, context):
        return

    clear_pending_year(context)
    clear_pending_city(context)

    language = preferred_language(update, context)

    try:
        query = parse_query(message.text)

    except ValueError:
        await reply(
            update,
            MESSAGES[language]['invalid_date'],
        )
        return

    state = user_state(context)

    # Язык пользователя имеет приоритет над языком парсера.
    saved_language = state.get('language') if state is not None else None

    if isinstance(saved_language, str) and saved_language in MESSAGES:
        language = saved_language
    elif query.language in MESSAGES:
        language = query.language

    if not query.city:
        await reply(
            update,
            MESSAGES[language]['parse_city'],
        )
        return

    try:
        # Геокодирование выполняется вне event loop.
        cities, suggested = await asyncio.to_thread(
            fetch_locations,
            query.city,
            language,
        )

    except (httpx.HTTPError, ValueError) as exc:
        LOGGER.exception(
            'Ошибка геокодирования: %s',
            exc,
        )

        await reply(
            update,
            MESSAGES[language]['error'],
        )
        return

    if not cities:
        await reply(
            update,
            MESSAGES[language]['not_found'].format(
                city=query.city,
            ),
        )
        return

    if len(cities) == 1 and not suggested:
        await respond_weather(
            update,
            context,
            cities[0],
            query,
            language,
        )
        return

    if state is None:
        LOGGER.warning('Невозможно сохранить список найденных городов')
        await reply(
            update,
            MESSAGES[language]['error'],
        )
        return

    # Сохраняем запрос для продолжения после выбора города.
    state['pending_query'] = query
    state['pending_cities'] = cities[:CITY_SELECTION_LIMIT]
    state['pending_language'] = language

    text = (
        MESSAGES[language]['suggestions'].format(city=query.city)
        if suggested
        else MESSAGES[language]['ambiguous']
    )

    sent_message = await reply(
        update,
        text,
        reply_markup=city_keyboard(cities),
    )

    if sent_message is not None:
        state['pending_city_message_id'] = sent_message.message_id
    else:
        clear_pending_city(context)


async def city_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Продолжает запрос после выбора населённого пункта."""
    callback = get_callback(update)

    if callback is None:
        return

    await callback.answer()

    state = user_state(context)

    if state is None:
        return

    cities = state.get('pending_cities')
    query = state.get('pending_query')

    language = stored_language(
        state,
        'pending_language',
        preferred_language(update, context),
    )

    message_id = state.get('pending_city_message_id')

    # Старые кнопки не должны использовать новый запрос.
    if (
        not isinstance(cities, list)
        or not isinstance(query, WeatherQuery)
        or message_id != callback_message_id(callback)
    ):
        await callback.edit_message_text(
            MESSAGES[language]['year_expired'],
        )
        return

    try:
        index = int(callback.data.split(':', maxsplit=1)[1])
    except (ValueError, IndexError):
        return

    if not 0 <= index < len(cities):
        await callback.edit_message_text(
            MESSAGES[language]['no_city'],
        )
        clear_pending_city(context)
        return

    city = cities[index]

    if not isinstance(city, dict):
        clear_pending_city(context)
        await callback.edit_message_text(
            MESSAGES[language]['no_city'],
        )
        return

    await callback.edit_message_text(
        f'📍 {city.get("name", "")}, '
        f'{city.get("country", "")}',
    )

    clear_pending_city(context)

    await respond_weather(
        update,
        context,
        city,
        query,
        language,
    )


async def year_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает выбор года через кнопки Telegram."""
    callback = get_callback(update)

    if callback is None:
        return

    await callback.answer()

    state = user_state(context)

    if state is None:
        return

    language = stored_language(
        state,
        'pending_year_language',
        preferred_language(update, context),
    )

    city = state.get('pending_year_city')
    query = state.get('pending_year_query')
    message_id = state.get('pending_year_message_id')

    if (
        not isinstance(city, dict)
        or not isinstance(query, WeatherQuery)
        or message_id != callback_message_id(callback)
    ):
        await callback.edit_message_text(
            MESSAGES[language]['year_expired'],
        )
        return

    value = callback.data.split(':', maxsplit=1)[1]

    if value == 'other':
        state['awaiting_year_input'] = True

        await callback.edit_message_text(
            MESSAGES[language]['year_input'],
        )
        return

    try:
        year = int(value)
    except ValueError:
        return

    await callback.edit_message_text(
        MESSAGES[language]['year_selected'].format(
            year=year,
        ),
    )

    await complete_year_selection(
        update,
        context,
        year,
    )


def main() -> None:
    """Запускает Telegram-бота через long polling."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
    )

    token = get_settings().telegram_bot_token.get_secret_value()

    persistence_path = Path('data/stormy_users.pkl')
    persistence_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    application = (
        Application.builder()
        .token(token)
        .persistence(
            PicklePersistence(
                filepath=persistence_path,
            ),
        )
        .build()
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('language', language_command))

    application.add_handler(
        CallbackQueryHandler(
            language_callback,
            pattern=r'^lang:(ru|en)$',
        ),
    )

    application.add_handler(
        CallbackQueryHandler(
            city_callback,
            pattern=r'^city:\d+$',
        ),
    )

    application.add_handler(
        CallbackQueryHandler(
            year_callback,
            pattern=r'^year:(?:\d{4}|other)$',
        ),
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text,
        ),
    )

    application.run_polling()


if __name__ == '__main__':
    main()

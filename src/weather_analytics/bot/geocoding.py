"""Нормализация географических названий для поиска в Open-Meteo.

Модуль приводит русскоязычные названия населённых пунктов
к возможной начальной форме с помощью pymorphy3.

Поддерживает простые названия, названия с дефисами
и составные названия из двух слов.

Исходное название всегда сохраняется как первый вариант
поиска, поскольку морфологический анализатор может
неправильно определить форму географического имени.
"""

from functools import lru_cache

import pymorphy3

from weather_analytics.bot.constants import (
    ADJECTIVE_TAG,
    CYRILLIC_LETTERS,
    GEOGRAPHICAL_TAG,
    MASCULINE_GENDER,
    NOMINATIVE_CASE,
)


@lru_cache(maxsize=1)
def get_morph_analyzer() -> pymorphy3.MorphAnalyzer:
    """Возвращает общий экземпляр морфологического анализатора.

    Анализатор создаётся только при первом обращении.
    Последующие вызовы используют экземпляр из кеша,
    что позволяет избежать повторной загрузки словарей.

    Returns:
        Экземпляр pymorphy3.MorphAnalyzer.
    """
    return pymorphy3.MorphAnalyzer()


def normalize_word(
    word: str,
    # Граммема, минимальное грамматическое значение в
    # системе морфологического описания.
    grammemes: set[str] | None = None,
) -> str:
    """Приводит слово к начальной или заданной грамматической форме.

    При неоднозначном разборе отдаёт предпочтение вариантам,
    помеченным pymorphy3 как географические названия.

    Args:
        word: Исходное слово.
        grammemes: Необязательные грамматические признаки
            для склонения слова.

    Returns:
        Нормализованное слово или форму с заданными признаками.
    """
    # Получаем возможные морфологические разборы слова.
    parses = get_morph_analyzer().parse(word)

    # Географический разбор предпочтительнее обычного.
    # Если таких разборов нет, используем исходный список.
    geographical = [parse for parse in parses if GEOGRAPHICAL_TAG in parse.tag]
    candidates = geographical or parses

    # Если задан набор грамматических признаков,
    # пытаемся получить соответствующую форму слова.
    if grammemes:
        for parse in candidates:
            inflected = parse.inflect(grammemes)

            if inflected:
                return inflected.word

    # Если склонение не запрашивалось или не удалось,
    # возвращаем начальную форму предпочтительного разбора.
    return candidates[0].normal_form


def normalize_city(name: str) -> str:
    """Приводит название населённого пункта к возможной начальной форме.

    Для кириллических названий использует pymorphy3.

    Отдельно обрабатывает названия с сочетанием «-на-»
    и составные названия из двух слов, где требуется
    согласование прилагательного с существительным.

    Названия без русских букв возвращает без изменений.

    Args:
        name: Исходное название населённого пункта.

    Returns:
        Возможная начальная форма географического названия.
    """
    original = name.strip()

    # Названия без русских букв не склоняем.
    # Это позволяет сохранить международное написание,
    # например London, Paris или New York.
    if not any(char in CYRILLIC_LETTERS for char in original.casefold()):
        return original

    # Обрабатываем названия с устойчивой частью «-на-».
    # Например: Ростове-на-Дону -> Ростов-на-Дону.
    #
    # Нормализуем только первую часть, а оставшуюся
    # сохраняем без изменений, поскольку она уже может
    # содержать правильную форму собственного имени.
    if '-на-' in original.casefold():
        separator_index = original.casefold().index('-на-')
        prefix = original[:separator_index]
        suffix = original[separator_index + len('-на-') :]

        return f'{normalize_word(prefix).capitalize()}-на-{suffix}'

    words = original.split()

    # Для названий из двух слов отдельно обрабатываем
    # существительное и согласованное с ним прилагательное.
    #
    # Например: Великом Новгороде -> Великий Новгород.
    if len(words) == 2:
        first, second = words
        analyzer = get_morph_analyzer()
        noun_parses = analyzer.parse(second)

        # Выбираем географический разбор существительного.
        # Если он отсутствует, используем первый вариант.
        noun = next(
            (parse for parse in noun_parses if GEOGRAPHICAL_TAG in parse.tag),
            noun_parses[0],
        )

        normalized_noun = noun.normal_form
        noun_gender = noun.tag.gender

        # Некоторые географические названия имеют несколько
        # морфологических разборов с одинаковой начальной
        # формой, но разным родом.
        #
        # Сохраняем существовавший приоритет мужского рода,
        # чтобы не изменить согласование составных названий.
        masculine = next(
            (
                parse
                for parse in noun_parses
                if parse.normal_form == normalized_noun
                and parse.tag.gender == MASCULINE_GENDER
            ),
            None,
        )

        if masculine:
            noun_gender = MASCULINE_GENDER

        # Если род существительного известен, пытаемся
        # поставить прилагательное в именительный падеж
        # соответствующего рода.
        if noun_gender:
            adjective_parses = analyzer.parse(first)
            normalized_first = None

            # Сохраняем исходный порядок разборов:
            # первый подходящий вариант имеет приоритет.
            for parse in adjective_parses:
                if ADJECTIVE_TAG not in parse.tag:
                    continue

                inflected = parse.inflect({NOMINATIVE_CASE, noun_gender})

                if inflected:
                    normalized_first = inflected.word
                    break

            # Если согласовать прилагательное не удалось,
            # используем обычную нормализацию слова.
            if normalized_first is None:
                normalized_first = normalize_word(first)

        else:
            # При неизвестном роде не пытаемся согласовать
            # слова, чтобы не получить произвольную форму.
            normalized_first = normalize_word(first)

        return f'{normalized_first.capitalize()} {normalized_noun.capitalize()}'

    # Для простых названий и названий с дефисами
    # нормализуем каждую часть отдельно.
    return '-'.join(normalize_word(part).capitalize() for part in original.split('-'))


def city_search_variants(name: str) -> list[str]:
    """Формирует варианты названия для поиска через Open-Meteo.

    Сначала сохраняет исходное написание, затем добавляет
    нормализованную форму, если она отличается.

    Порядок важен: исходное название должно проверяться
    раньше результата морфологического анализа.

    Args:
        name: Название населённого пункта.

    Returns:
        Список уникальных непустых вариантов поиска.
    """
    original = name.strip()
    normalized = normalize_city(original)

    # dict.fromkeys сохраняет порядок появления значений
    # и одновременно удаляет повторяющиеся варианты.
    return list(dict.fromkeys(variant for variant in (original, normalized) if variant))

"""Поиск населённых пунктов для Telegram-бота Stormy.

Подготавливает варианты названий, выполняет поиск через
Open-Meteo Geocoding API, удаляет дубликаты и ранжирует
точные и приблизительные совпадения.

Поддерживает морфологическую нормализацию и ограниченный
поиск названий с опечатками без ручного справочника городов.
"""

from difflib import SequenceMatcher
from typing import Any

from weather_analytics.api import OpenMeteoClient
from weather_analytics.api.constants import (
    DEFAULT_RESULT_COUNT,
    MAX_RESULT_COUNT,
)
from weather_analytics.bot.constants import (
    CITY_SELECTION_LIMIT,
    COMMON_REPLACEMENTS,
    MAX_FUZZY_REQUESTS,
    MIN_EXACT_CITY_POPULATION,
    MIN_PREFIX_LENGTH,
    MIN_SIMILARITY,
    PREFIX_DIVISOR,
    PREFIX_TRIM_LENGTH,
    SIMILARITY_TOLERANCE,
    SUGGESTION_LIMIT,
)
from weather_analytics.bot.geocoding import city_search_variants

type City = dict[str, Any]
type CityKey = int | tuple[str | None, str | None]


def city_population(city: City) -> int:
    """Возвращает численность населения для сортировки городов."""
    return city.get('population') or 0


def unique_named_cities(cities: list[City]) -> list[City]:
    """Удаляет одинаково названные города в одном регионе и стране.

    Предпочитает запись с наибольшим известным населением.
    Если население отсутствует у всех совпадений, сохраняет
    их как потенциально разные географические объекты.
    """
    unique: list[City] = []
    seen: set[tuple[str, str, str]] = set()

    for city in cities:
        population = city_population(city)

        # Не объединяем записи без населения, поскольку они
        # могут обозначать разные географические объекты.
        if not population:
            unique.append(city)
            continue

        key = (
            (city.get('name') or '').casefold(),
            (city.get('admin1') or '').casefold(),
            (city.get('country') or '').casefold(),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(city)

    # Записи без населения скрываем, только если уже найден
    # населённый город с тем же названием, регионом и страной.
    populated_keys = {
        (
            (city.get('name') or '').casefold(),
            (city.get('admin1') or '').casefold(),
            (city.get('country') or '').casefold(),
        )
        for city in unique
        if city_population(city)
    }

    return [
        city
        for city in unique
        if city_population(city)
        or (
            (city.get('name') or '').casefold(),
            (city.get('admin1') or '').casefold(),
            (city.get('country') or '').casefold(),
        )
        not in populated_keys
    ]


def city_similarity(name: str, city: City) -> float:
    """Вычисляет сходство названия с результатом геокодирования."""
    return SequenceMatcher(
        None,
        name.casefold(),
        (city.get('name') or '').casefold(),
    ).ratio()


def city_key(city: City) -> CityKey:
    """Возвращает ключ для удаления повторяющихся результатов."""
    identifier = city.get('id')

    if identifier is not None:
        return identifier

    return city.get('name'), city.get('country')


def add_candidates(
    candidates: dict[CityKey, City],
    cities: list[City],
) -> None:
    """Добавляет результаты геокодирования без дубликатов."""
    for city in cities:
        candidates[city_key(city)] = city


def search_prefixes(name: str) -> list[str]:
    """Формирует префиксы для поиска приблизительных совпадений."""
    lengths = (
        max(
            MIN_PREFIX_LENGTH,
            len(name) - PREFIX_TRIM_LENGTH,
        ),
        max(
            MIN_PREFIX_LENGTH,
            len(name) // PREFIX_DIVISOR,
        ),
    )

    prefixes = (name[:length].strip(' -') for length in lengths)

    return list(
        dict.fromkeys(prefix for prefix in prefixes if len(prefix) >= MIN_PREFIX_LENGTH)
    )


def typo_variants(name: str) -> list[str]:
    """Формирует варианты названия с одной опечаткой.

    Сначала переставляет соседние символы с конца названия,
    затем применяет распространённые замены русских гласных.
    """
    variants = []

    # Проверяем перестановки с конца, чтобы быстрее находить
    # ошибки в окончаниях, например Dubia -> Dubai.
    for index in range(len(name) - 2, -1, -1):
        if name[index] == name[index + 1]:
            continue

        variant = name[:index] + name[index + 1] + name[index] + name[index + 2 :]
        variants.append(variant)

    # Проверяем распространённые замены русских гласных.
    for index, letter in enumerate(name):
        replacement = COMMON_REPLACEMENTS.get(letter.casefold())

        if replacement:
            variants.append(name[:index] + replacement + name[index + 1 :])

    return list(dict.fromkeys(variant for variant in variants if variant != name))


def rank_candidates(
    candidates: dict[CityKey, City],
    variants: list[str],
) -> list[City]:
    """Ранжирует похожие города по сходству и населению.

    Отбрасывает результаты с недостаточным сходством.
    Для близких вариантов учитывает численность населения.
    """
    scored = []

    for city in candidates.values():
        similarity = max(city_similarity(variant, city) for variant in variants)

        if similarity >= MIN_SIMILARITY:
            scored.append(
                (
                    similarity,
                    city_population(city),
                    city,
                )
            )

    if not scored:
        return []

    best_similarity = max(similarity for similarity, _, _ in scored)

    # Население влияет на порядок только у кандидатов,
    # находящихся достаточно близко к лучшему совпадению.
    scored.sort(
        key=lambda item: (
            item[0] >= best_similarity - SIMILARITY_TOLERANCE,
            item[1] if item[0] >= best_similarity - SIMILARITY_TOLERANCE else item[0],
            item[0],
        ),
        reverse=True,
    )

    return [city for _, _, city in scored[:SUGGESTION_LIMIT]]


class CitySearchService:
    """Ищет населённые пункты через Open-Meteo Geocoding API."""

    def __init__(self, client: OpenMeteoClient) -> None:
        """Сохраняет API-клиент."""
        self.client = client

    def find_cities(
        self,
        name: str,
        language: str,
    ) -> list[City]:
        """Возвращает точные совпадения названия города."""
        variants = city_search_variants(name)
        exact_names = {variant.casefold() for variant in variants}
        candidates: dict[CityKey, City] = {}

        for variant in variants:
            cities = self.client.find_locations(
                city=variant,
                language=language,
                count=MAX_RESULT_COUNT,
            )
            add_candidates(candidates, cities)

        exact = [
            city
            for city in candidates.values()
            if (city.get('name') or '').casefold() in exact_names
        ]

        exact.sort(
            key=city_population,
            reverse=True,
        )

        return unique_named_cities(exact)[:DEFAULT_RESULT_COUNT]

    def suggest_cities(
        self,
        name: str,
        language: str,
    ) -> list[City]:
        """Подбирает похожие города по префиксам и опечаткам."""
        variants = city_search_variants(name)
        candidates: dict[CityKey, City] = {}

        # Сначала собираем кандидатов по префиксам.
        prefixes = list(
            dict.fromkeys(
                prefix for variant in variants for prefix in search_prefixes(variant)
            )
        )

        for prefix in prefixes:
            cities = self.client.find_locations(
                city=prefix,
                language=language,
                count=MAX_RESULT_COUNT,
            )
            add_candidates(candidates, cities)

        # Затем проверяем ограниченное число исправлений.
        fuzzy_names = list(
            dict.fromkeys(
                corrected
                for variant in variants
                for corrected in typo_variants(variant)
            )
        )

        for corrected in fuzzy_names[:MAX_FUZZY_REQUESTS]:
            cities = self.client.find_locations(
                city=corrected,
                language=language,
                count=MAX_RESULT_COUNT,
            )
            add_candidates(candidates, cities)

        return rank_candidates(candidates, variants)

    def search_cities(
        self,
        name: str,
        language: str,
    ) -> tuple[list[City], bool]:
        """Возвращает города для Telegram и признак предложений.

        Если найден достаточно населённый город с точным
        названием, возвращает точные совпадения.

        Если точных совпадений нет или они малонаселённые,
        дополнительно проверяет возможные опечатки.

        Второй элемент результата показывает, использовался
        ли поиск похожих названий.
        """
        exact = self.find_cities(name, language)

        # Для распространённых городов точного поиска достаточно.
        if exact and city_population(exact[0]) >= MIN_EXACT_CITY_POPULATION:
            return exact[:CITY_SELECTION_LIMIT], False

        suggestions = self.suggest_cities(name, language)

        if not suggestions:
            return exact[:CITY_SELECTION_LIMIT], False

        # Предложения ставим первыми, но обязательно сохраняем
        # хотя бы одно точное совпадение, если оно существует.
        candidates: dict[CityKey, City] = {}

        if exact:
            add_candidates(
                candidates,
                suggestions[: CITY_SELECTION_LIMIT - 1],
            )
            add_candidates(candidates, exact[:1])
        else:
            add_candidates(
                candidates,
                suggestions[:CITY_SELECTION_LIMIT],
            )

        return list(candidates.values()), True

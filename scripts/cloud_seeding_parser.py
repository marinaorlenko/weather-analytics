"""Автоматический сбор статистики засева облаков в ОАЭ за 2016–2026 годы."""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from IPython.display import display

START_YEAR = 2016
END_YEAR = 2026
OUTPUT_DIR = Path('data/external')

SOURCES = [
    'https://www.thenationalnews.com/uae/environment/seeding-flights-in-uae-boosting-rainfall-from-clouds-by-a-third-1.694589',
    'https://gulfnews.com/uae/environment/10-15-of-uaes-rain-in-2018-caused-by-cloud-seeding-1.61188081',
    'https://www.thenationalnews.com/uae/environment/uae-aims-to-boost-cloud-seeding-via-artificial-clouds-says-top-meteorologist-1.966292',
    'https://www.gulftoday.ae/News/2022/01/01/UAE-carried-out-299-cloud-seeding-operations-in-2021',
    'https://www.thenationalnews.com/uae/2023/01/24/uae-doubles-number-of-cloud-seeding-flights-in-six-years-in-bid-to-boost-rainfall/',
    'https://gulfnews.com/uae/weather/uae-conducts-172-cloud-seeding-flights-in-2025-so-far-1.500228558',
    'https://gulfnews.com/uae/weather/uae-flies-110-cloud-seeding-missions-in-2026-with-rain-forecast-from-monday-1.500627473',
    'https://www.khaleejtimes.com/uae/weather/uae-why-less-rainfall-this-year',
    'https://www.thenationalnews.com/climate/environment/2023/08/30/uae-launches-new-cloud-seeding-campaign-to-boost-rainfall/',
    'https://www.khaleejtimes.com/uae/weather/more-rains-in-uae-cloud-seeding-operations-resume-in-2024',
    'https://gulfnews.com/uae/environment/revealed-how-much-rain-fell-due-to-cloud-seeding-in-uae-1.69106071',
    'https://www.khaleejtimes.com/uae/weather/uae-39-cloud-seeding-missions-july-2025',
]

NUMBER = r'\d{1,3}(?:,\d{3})*'
YEAR = r'20(?:1[6-9]|2[0-6])'
METRIC = (
    r'(?:(?:cloud[\s-]*seeding|rain[\s-]*enhancement)\s+)?'
    r'(?P<metric>operations?|missions?|flights?|sorties)'
)
ACTION = r'(?:conducted|carried\s+out|completed|performed|recorded|flew)'

# Прямое указание количества и единицы измерения.
COUNT_METRIC = re.compile(
    rf'\b(?P<count>{NUMBER})\s+{METRIC}\b',
    re.IGNORECASE,
)

# Сравнения: "with 177 carried out in 2016",
# "compared to 399 in 2020".
COMPARISON = re.compile(
    rf'\b(?:with|compared\s+to|versus|vs\.?)\s+'
    rf'(?P<count>{NUMBER})'
    rf'(?:\s+(?:{ACTION}|operations?|missions?|flights?))?'
    rf'.{{0,40}}?\b(?:in|during|for)\s+'
    rf'(?P<year>{YEAR})\b',
    re.IGNORECASE,
)

YEAR_REFERENCE = re.compile(
    rf'\b(?:in|during|for|throughout)\s+(?P<year>{YEAR})\b',
    re.IGNORECASE,
)

RELATIVE_YEAR = re.compile(
    r'\b(?:last\s+year|previous\s+year)\b',
    re.IGNORECASE,
)

PARTIAL_MARKERS = re.compile(
    r'\b(?:so\s+far|year[\s-]*to[\s-]*date|'
    r'since\s+the\s+(?:start|beginning)|'
    r'as\s+of|to\s+date|'
    r'first\s+(?:half|quarter|\d+\s+months?)|'
    r'up\s+to)\b',
    re.IGNORECASE,
)

MONTHS = (
    'january|february|march|april|may|june|july|'
    'august|september|october|november|december'
)

MONTHLY_MARKERS = re.compile(
    rf'\b(?:in|during|for)\s+(?:the\s+month\s+of\s+)?'
    rf'(?:{MONTHS})\b',
    re.IGNORECASE,
)

APPROXIMATE_MARKERS = re.compile(
    r'\b(?:about|around|approximately|roughly|'
    r'nearly|almost|more\s+than|over|at\s+least)\b',
    re.IGNORECASE,
)


def parse_date(value):
    """Преобразовать дату публикации в объект date."""
    if not value:
        return None

    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def get_json_dates(data):
    """Извлечь даты публикации из JSON-LD с типом Article или NewsArticle."""
    dates = []

    if isinstance(data, dict):
        types = data.get('@type', [])
        types = [types] if isinstance(types, str) else types

        if any(
            item in {'Article', 'NewsArticle', 'ReportageNewsArticle'} for item in types
        ):
            parsed = parse_date(data.get('datePublished'))
            if parsed:
                dates.append(parsed)

        for value in data.values():
            if isinstance(value, (dict, list)):
                dates.extend(get_json_dates(value))

    elif isinstance(data, list):
        for item in data:
            dates.extend(get_json_dates(item))

    return dates


def get_publication_date(soup, url):
    """Определить дату именно статьи, исключая даты соседних публикаций."""
    for attribute, value in [
        ('property', 'article:published_time'),
        ('name', 'datePublished'),
        ('itemprop', 'datePublished'),
        ('name', 'pubdate'),
    ]:
        tag = soup.find('meta', attrs={attribute: value})

        if tag:
            parsed = parse_date(tag.get('content'))
            if parsed:
                return parsed

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '{}')
            dates = get_json_dates(data)

            if dates:
                return min(dates)
        except (json.JSONDecodeError, TypeError):
            continue

    # Для URL с датой используем её как резервный источник.
    match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)

    if match:
        try:
            return date(*map(int, match.groups()))
        except ValueError:
            pass

    return None


def fetch_article(url, session):
    """Загрузить статью и выделить заголовки, текст и дату публикации."""
    response = session.get(url, timeout=25)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    publication_date = get_publication_date(soup, url)

    for element in soup(['script', 'style', 'nav', 'footer', 'aside']):
        element.decompose()

    article = soup.find('article') or soup.find('main') or soup
    elements = article.find_all(['h1', 'h2', 'h3', 'p'])

    if not elements:
        elements = [article]

    paragraphs = []
    seen = set()

    for element in elements:
        text = re.sub(
            r'\s+',
            ' ',
            element.get_text(' ', strip=True),
        ).strip()

        if text and text not in seen:
            paragraphs.append(text)
            seen.add(text)

    return paragraphs, publication_date


def find_year(sentence, position, publication_date):
    """Определить год по ближайшему указанию или относительной дате."""
    candidates = []

    for match in YEAR_REFERENCE.finditer(sentence):
        distance = min(
            abs(position - match.start()),
            abs(position - match.end()),
        )

        if distance <= 120:
            candidates.append((distance, int(match.group('year'))))

    for match in RELATIVE_YEAR.finditer(sentence):
        if publication_date:
            distance = abs(position - match.start())

            if distance <= 100:
                candidates.append((distance, publication_date.year - 1))

    if candidates:
        return min(candidates)[1]

    if publication_date and PARTIAL_MARKERS.search(sentence):
        return publication_date.year

    return None


def classify_period(sentence, year, publication_date):
    """Определить полноту периода и статус достоверности."""
    if publication_date and year > publication_date.year:
        return 'unknown_period', 'date_conflict'

    if PARTIAL_MARKERS.search(sentence):
        return 'partial_year', 'candidate'

    if publication_date and year == publication_date.year:
        if publication_date.month < 12:
            return 'partial_year', 'candidate'

        return 'unknown_period', 'needs_review'

    if publication_date is None:
        return 'unknown_period', 'needs_review'

    return 'full_year', 'candidate'


def extract_records(url, session):
    """Извлечь год, количество и исходную единицу измерения."""
    paragraphs, publication_date = fetch_article(url, session)
    records = []
    source = urlparse(url).netloc

    for paragraph in paragraphs:
        sentences = re.split(
            r'(?<=[.!?])\s+(?=[A-Z])',
            paragraph,
        )

        for sentence in sentences:
            if not re.search(
                r'cloud[\s-]*seed|rain[\s-]*enhancement',
                sentence,
                re.IGNORECASE,
            ):
                continue

            matches = []

            for match in COUNT_METRIC.finditer(sentence):
                matches.append(
                    {
                        'position': match.start(),
                        'count': int(match.group('count').replace(',', '')),
                        'metric_type': match.group('metric').lower(),
                        'explicit_year': None,
                    }
                )

            # Для сравнений наследуем единицу измерения из предложения.
            for match in COMPARISON.finditer(sentence):
                metrics = list(COUNT_METRIC.finditer(sentence))

                metric_type = (
                    metrics[0].group('metric').lower() if metrics else 'unspecified'
                )

                matches.append(
                    {
                        'position': match.start(),
                        'count': int(match.group('count').replace(',', '')),
                        'metric_type': metric_type,
                        'explicit_year': int(match.group('year')),
                    }
                )

            seen = set()

            for item in matches:
                year = item['explicit_year'] or find_year(
                    sentence,
                    item['position'],
                    publication_date,
                )

                if year is None or not START_YEAR <= year <= END_YEAR:
                    continue

                key = (
                    year,
                    item['count'],
                    item['metric_type'],
                )

                if key in seen:
                    continue

                seen.add(key)

                period_type, status = classify_period(
                    sentence,
                    year,
                    publication_date,
                )

                prefix = sentence[max(0, item['position'] - 25) : item['position']]

                if APPROXIMATE_MARKERS.search(prefix):
                    status = 'approximate'

                if MONTHLY_MARKERS.search(sentence):
                    status = 'monthly_value'

                records.append(
                    {
                        'year': year,
                        'operations': item['count'],
                        'metric_type': item['metric_type'],
                        'period_type': period_type,
                        'source': source,
                        'source_url': url,
                        'source_date': (
                            publication_date.isoformat() if publication_date else None
                        ),
                        'source_context': sentence[:700],
                        'extraction_status': status,
                    }
                )

    return records


def build_dataset(sources):
    """Собрать годовой ряд и сохранить неоднозначные значения отдельно."""
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    records = []
    errors = []

    for url in dict.fromkeys(sources):
        try:
            records.extend(extract_records(url, session))
        except requests.RequestException as error:
            errors.append(
                {
                    'url': url,
                    'error': str(error),
                }
            )

    candidates = pd.DataFrame(
        records,
        columns=[
            'year',
            'operations',
            'metric_type',
            'period_type',
            'source',
            'source_url',
            'source_date',
            'source_context',
            'extraction_status',
        ],
    ).drop_duplicates()

    results = []

    for year in range(START_YEAR, END_YEAR + 1):
        year_data = candidates[candidates['year'] == year]
        valid = year_data[year_data['extraction_status'] == 'candidate']

        full = valid[valid['period_type'] == 'full_year']
        partial = valid[valid['period_type'] == 'partial_year']

        result = {
            'year': year,
            'operations': pd.NA,
            'metric_type': pd.NA,
            'period_start': pd.NA,
            'period_end': pd.NA,
            'period_type': pd.NA,
            'geography': 'UAE',
            'source': pd.NA,
            'source_url': pd.NA,
            'source_context': pd.NA,
            'verification_status': 'missing',
        }

        if not full.empty:
            selected = full
        elif not partial.empty:
            # Выбираем самую позднюю накопленную статистику.
            partial = partial.sort_values(
                'source_date',
                ascending=False,
                na_position='last',
            )

            latest_date = partial.iloc[0]['source_date']
            selected = partial[partial['source_date'] == latest_date]
        else:
            if not year_data.empty:
                result['verification_status'] = 'needs_review'

            results.append(result)
            continue

        # Сравниваем одновременно числа и единицы измерения.
        unique_values = selected[['operations', 'metric_type']].drop_duplicates()

        if len(unique_values) != 1:
            result['period_type'] = selected.iloc[0]['period_type']
            result['verification_status'] = 'conflict'
            results.append(result)
            continue

        row = selected.iloc[0]

        result.update(
            {
                'operations': int(row['operations']),
                'metric_type': row['metric_type'],
                'period_start': f'{year}-01-01',
                'period_end': (
                    f'{year}-12-31'
                    if row['period_type'] == 'full_year'
                    else row['source_date']
                ),
                'period_type': row['period_type'],
                'source': row['source'],
                'source_url': row['source_url'],
                'source_context': row['source_context'],
                'verification_status': 'auto_extracted',
            }
        )

        results.append(result)

    return (
        pd.DataFrame(results),
        candidates,
        pd.DataFrame(errors, columns=['url', 'error']),
    )


# Сохраняем итоговые данные, кандидатов и ошибки.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df_seeding, df_candidates, df_errors = build_dataset(SOURCES)

df_seeding.to_csv(
    OUTPUT_DIR / 'uae_cloud_seeding_operations_auto.csv',
    index=False,
    encoding='utf-8-sig',
)

df_candidates.to_csv(
    OUTPUT_DIR / 'uae_cloud_seeding_candidates_auto.csv',
    index=False,
    encoding='utf-8-sig',
)

df_errors.to_csv(
    OUTPUT_DIR / 'uae_cloud_seeding_errors_auto.csv',
    index=False,
    encoding='utf-8-sig',
)

display(
    df_seeding[
        [
            'year',
            'operations',
            'metric_type',
            'period_type',
            'period_end',
            'verification_status',
            'source_url',
        ]
    ]
)

print(f'Извлечено кандидатов: {len(df_candidates)}')
print(f'Ошибок загрузки: {len(df_errors)}')
print(
    'Годов без однозначного результата:',
    df_seeding['operations'].isna().sum(),
)

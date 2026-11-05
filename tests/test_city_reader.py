"""Тесты чтения и проверки справочника городов."""

import csv

import pytest

from weather_analytics.etl.city_reader import CityReader
from weather_analytics.models.weather import Location


@pytest.fixture
def csv_file(tmp_path):
    """Создаёт временный CSV-файл с корректными данными."""
    file_path = tmp_path / 'capitals.csv'

    rows = [
        {
            'country': 'United Arab Emirates',
            'iso2': 'AE',
            'capital': 'Abu Dhabi',
            'latitude': '24.4539',
            'longitude': '54.3773',
            'timezone': 'Asia/Dubai',
            'territory_type': 'sovereign',
            'verification': 'verified',
        },
        {
            'country': 'Germany',
            'iso2': 'DE',
            'capital': 'Berlin',
            'latitude': '52.5200',
            'longitude': '13.4050',
            'timezone': 'Europe/Berlin',
            'territory_type': 'sovereign',
            'verification': 'verified',
        },
    ]

    # Создаём тестовый файл независимо от основного справочника.
    with file_path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return file_path


def test_read_success(csv_file):
    """Проверяет чтение CSV и создание объектов Location."""
    locations = CityReader(csv_file).read()

    assert len(locations) == 2
    assert all(isinstance(location, Location) for location in locations)
    assert locations[0].name == 'Abu Dhabi'
    assert locations[0].country == 'United Arab Emirates'
    assert locations[0].latitude == 24.4539
    assert locations[1].timezone == 'Europe/Berlin'


def test_read_missing_column(csv_file):
    """Проверяет ошибку при отсутствии обязательной колонки."""
    content = csv_file.read_text(encoding='utf-8')
    content = content.replace('timezone,', '')

    csv_file.write_text(content, encoding='utf-8')

    with pytest.raises(ValueError, match='отсутствуют колонки'):
        CityReader(csv_file).read()


@pytest.mark.parametrize(
    ('original', 'invalid', 'message'),
    [
        ('24.4539', '95.0', 'Некорректная широта'),
        ('54.3773', '200.0', 'Некорректная долгота'),
    ],
)
def test_read_invalid_coordinates(csv_file, original, invalid, message):
    """Проверяет отклонение координат за допустимыми пределами."""
    content = csv_file.read_text(encoding='utf-8')
    csv_file.write_text(
        content.replace(original, invalid),
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match=message):
        CityReader(csv_file).read()


def test_read_invalid_timezone(csv_file):
    """Проверяет ошибку при неизвестном часовом поясе."""
    content = csv_file.read_text(encoding='utf-8')
    content = content.replace('Asia/Dubai', 'Invalid/Timezone')

    csv_file.write_text(content, encoding='utf-8')

    with pytest.raises(ValueError, match='Некорректный часовой пояс'):
        CityReader(csv_file).read()


def test_read_duplicate_city(csv_file):
    """Проверяет обнаружение повторяющегося города."""
    with csv_file.open('a', encoding='utf-8') as file:
        file.write(
            'Germany,DE,Berlin,52.5200,13.4050,'
            'Europe/Berlin,sovereign,verified\n'
        )

    with pytest.raises(ValueError, match='Повторяющийся город'):
        CityReader(csv_file).read()


def test_read_headers_without_rows(csv_file):
    """Проверяет ошибку при наличии заголовков без городов."""
    header = csv_file.read_text(encoding='utf-8').splitlines()[0]
    csv_file.write_text(header + '\n', encoding='utf-8')

    with pytest.raises(ValueError, match='Справочник городов пуст'):
        CityReader(csv_file).read()


def test_read_missing_value(csv_file):
    """Проверяет обнаружение пустого обязательного поля."""
    content = csv_file.read_text(encoding='utf-8')
    content = content.replace('Abu Dhabi', '')

    csv_file.write_text(content, encoding='utf-8')

    with pytest.raises(ValueError, match='Пустое обязательное поле'):
        CityReader(csv_file).read()

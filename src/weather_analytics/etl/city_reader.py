"""Чтение и проверка справочника столиц и административных центров."""

import csv
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from weather_analytics.models.weather import Location


class CityReader:
    """Загружает географические точки из CSV в объекты Location."""

    REQUIRED_COLUMNS = {
        'country',
        'iso2',
        'capital',
        'latitude',
        'longitude',
        'timezone',
        'territory_type',
        'verification',
    }

    def __init__(self, file_path: str | Path) -> None:
        """Сохраняет путь к CSV-файлу со справочником городов."""
        self.file_path = Path(file_path)

    def read(self) -> list[Location]:
        """Читает CSV, проверяет записи и возвращает список городов."""
        locations: list[Location] = []
        seen_codes: set[tuple[str, str]] = set()

        # Читаем справочник с поддержкой UTF-8 и возможного BOM.
        with self.file_path.open(
            encoding='utf-8-sig',
            newline='',
        ) as file:
            reader = csv.DictReader(file)

            # Проверяем наличие всех обязательных колонок.
            if not reader.fieldnames:
                raise ValueError('CSV-файл не содержит заголовков')

            missing = self.REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing:
                raise ValueError(
                    f'В CSV отсутствуют колонки: {sorted(missing)}'
                )

            for line_number, row in enumerate(reader, start=2):
                # Проверяем заполненность всех обязательных полей.
                if any(
                    not row.get(column) or not row[column].strip()
                    for column in self.REQUIRED_COLUMNS
                ):
                    raise ValueError(
                        f'Пустое обязательное поле в строке {line_number}'
                    )

                # Преобразуем координаты в числа и проверяем диапазоны.
                try:
                    latitude = float(row['latitude'])
                    longitude = float(row['longitude'])
                except ValueError as error:
                    raise ValueError(
                        f'Некорректные координаты в строке {line_number}'
                    ) from error

                if not isfinite(latitude) or not -90 <= latitude <= 90:
                    raise ValueError(
                        f'Некорректная широта в строке {line_number}'
                    )

                if not isfinite(longitude) or not -180 <= longitude <= 180:
                    raise ValueError(
                        f'Некорректная долгота в строке {line_number}'
                    )

                # Проверяем, что часовой пояс известен базе IANA.
                try:
                    ZoneInfo(row['timezone'])
                except ZoneInfoNotFoundError as error:
                    raise ValueError(
                        f'Некорректный часовой пояс '
                        f'в строке {line_number}: {row["timezone"]}'
                    ) from error

                # Один ISO-код может встречаться у нескольких городов
                # одной территории, поэтому проверяем сочетание полей.
                unique_key = (
                    row['iso2'],
                    row['capital'].casefold(),
                )

                if unique_key in seen_codes:
                    raise ValueError(
                        f'Повторяющийся город в строке {line_number}: '
                        f'{row["capital"]}'
                    )

                seen_codes.add(unique_key)

                # Создаём объект существующей модели Location.
                locations.append(
                    Location(
                        name=row['capital'],
                        country=row['country'],
                        latitude=latitude,
                        longitude=longitude,
                        timezone=row['timezone'],
                    )
                )

        if not locations:
            raise ValueError('Справочник городов пуст')

        return locations

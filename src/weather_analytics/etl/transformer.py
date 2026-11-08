"""Преобразование погодных данных Open-Meteo для PostgreSQL."""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from weather_analytics.etl.field_mappings import (
    ECMWF_HOURLY_FIELDS,
    FORECAST_DAILY_FIELDS,
    FORECAST_HOURLY_FIELDS,
    HISTORICAL_DAILY_FIELDS,
    HISTORICAL_HOURLY_FIELDS,
)
from weather_analytics.models.weather import Location


class WeatherTransformer:
    """Преобразует ответы Open-Meteo в записи для базы данных."""

    @staticmethod
    def _extract_fields(
        values: dict[str, Any],
        index: int,
        mapping: dict[str, str],
    ) -> dict[str, Any]:
        """Преобразует показатели API в названия столбцов PostgreSQL.

        Отсутствующие необязательные показатели заменяются на None.
        Для неполных массивов формируется информативная ошибка.
        """
        result: dict[str, Any] = {}

        for field, column in mapping.items():
            if field not in values:
                result[column] = None
                continue

            field_values = values[field]

            if not isinstance(field_values, list):
                raise ValueError(f'Поле Open-Meteo {field!r} должно содержать список')

            if index >= len(field_values):
                raise ValueError(
                    f'Недостаточно значений в поле Open-Meteo '
                    f'{field!r}: отсутствует индекс {index}'
                )

            result[column] = field_values[index]

        return result

    @staticmethod
    def _optional_value(
        values: dict[str, Any],
        field: str,
        index: int,
    ) -> Any:
        """Возвращает необязательный показатель с проверкой длины."""
        if field not in values:
            return None

        field_values = values[field]

        if not isinstance(field_values, list):
            raise ValueError(f'Поле Open-Meteo {field!r} должно содержать список')

        if index >= len(field_values):
            raise ValueError(
                f'Недостаточно значений в поле Open-Meteo '
                f'{field!r}: отсутствует индекс {index}'
            )

        return field_values[index]

    @staticmethod
    def _parse_local_datetime(
        value: str | None,
        timezone_name: str,
    ) -> datetime | None:
        """Преобразует местное время города в datetime с часовым поясом."""
        if value is None:
            return None

        # Время восхода и заката Open-Meteo возвращает
        # в местном часовом поясе выбранного города.
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is not None:
            return parsed.astimezone(ZoneInfo(timezone_name))

        return parsed.replace(tzinfo=ZoneInfo(timezone_name))

    @staticmethod
    def _validate_fetched_at(fetched_at: datetime) -> None:
        """Проверяет наличие часового пояса у времени прогноза."""
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError('Время получения прогноза должно содержать часовой пояс')

    @staticmethod
    def _parse_utc_timestamp(timestamp: int | float) -> datetime:
        """Преобразует Unix timestamp в дату и время UTC."""
        return datetime.fromtimestamp(
            timestamp,
            tz=UTC,
        )

    @staticmethod
    def _parse_is_day(
        values: dict[str, Any],
        index: int,
    ) -> bool | None:
        """Преобразует показатель дня и ночи в логическое значение."""
        value = WeatherTransformer._optional_value(
            values,
            'is_day',
            index,
        )

        if value is None:
            return None

        if value not in (0, 1):
            raise ValueError(f'Некорректное значение is_day: {value!r}')

        return bool(value)

    @staticmethod
    def transform_historical_daily(
        location: Location,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Преобразует суточные исторические показатели в записи."""
        daily = data['daily']
        records = []

        # Каждая дата образует отдельную запись PostgreSQL.
        for index, day in enumerate(daily['time']):
            record = {
                'weather_date': datetime.fromisoformat(day).date(),
                **WeatherTransformer._extract_fields(
                    daily,
                    index,
                    HISTORICAL_DAILY_FIELDS,
                ),
                'sunrise': WeatherTransformer._parse_local_datetime(
                    WeatherTransformer._optional_value(
                        daily,
                        'sunrise',
                        index,
                    ),
                    location.timezone,
                ),
                'sunset': WeatherTransformer._parse_local_datetime(
                    WeatherTransformer._optional_value(
                        daily,
                        'sunset',
                        index,
                    ),
                    location.timezone,
                ),
            }

            records.append(record)

        return records

    @staticmethod
    def transform_historical_hourly(
        location: Location,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Преобразует почасовую историю с Unix timestamp во время UTC."""
        hourly = data['hourly']
        records = []

        # Unix timestamp сохраняет однозначное время даже
        # при переходах между летним и зимним временем.
        for index, timestamp in enumerate(hourly['time']):
            record = {
                'weather_time': WeatherTransformer._parse_utc_timestamp(
                    timestamp,
                ),
                **WeatherTransformer._extract_fields(
                    hourly,
                    index,
                    HISTORICAL_HOURLY_FIELDS,
                ),
                'is_day': WeatherTransformer._parse_is_day(
                    hourly,
                    index,
                ),
            }

            records.append(record)

        return records

    @staticmethod
    def transform_forecast_daily(
        location: Location,
        data: dict[str, Any],
        fetched_at: datetime,
    ) -> list[dict[str, Any]]:
        """Преобразует суточный прогноз в записи PostgreSQL."""
        WeatherTransformer._validate_fetched_at(fetched_at)

        daily = data['daily']
        records = []

        # Все строки одного прогнозного снимка
        # используют единое время его получения.
        for index, day in enumerate(daily['time']):
            record = {
                'forecast_date': datetime.fromisoformat(day).date(),
                'fetched_at': fetched_at,
                **WeatherTransformer._extract_fields(
                    daily,
                    index,
                    FORECAST_DAILY_FIELDS,
                ),
                'sunrise': WeatherTransformer._parse_local_datetime(
                    WeatherTransformer._optional_value(
                        daily,
                        'sunrise',
                        index,
                    ),
                    location.timezone,
                ),
                'sunset': WeatherTransformer._parse_local_datetime(
                    WeatherTransformer._optional_value(
                        daily,
                        'sunset',
                        index,
                    ),
                    location.timezone,
                ),
            }

            records.append(record)

        return records

    @staticmethod
    def transform_forecast_hourly(
        location: Location,
        data: dict[str, Any],
        fetched_at: datetime,
    ) -> list[dict[str, Any]]:
        """Преобразует почасовой прогноз в записи PostgreSQL."""
        WeatherTransformer._validate_fetched_at(fetched_at)

        hourly = data['hourly']
        records = []

        # Преобразуем временные метки в UTC.
        # fetched_at связывает строки с одним прогнозным снимком.
        for index, timestamp in enumerate(hourly['time']):
            record = {
                'forecast_time': WeatherTransformer._parse_utc_timestamp(
                    timestamp,
                ),
                'fetched_at': fetched_at,
                **WeatherTransformer._extract_fields(
                    hourly,
                    index,
                    FORECAST_HOURLY_FIELDS,
                ),
                'is_day': WeatherTransformer._parse_is_day(
                    hourly,
                    index,
                ),
            }

            records.append(record)

        return records

    @staticmethod
    def transform_ecmwf_hourly(
        location: Location,
        data: dict[str, Any],
        fetched_at: datetime,
    ) -> list[dict[str, Any]]:
        """Преобразует специализированный почасовой прогноз ECMWF."""
        WeatherTransformer._validate_fetched_at(fetched_at)

        hourly = data['hourly']

        # ECMWF хранится как отдельный набор показателей.
        # Отсутствующие необязательные значения остаются NULL.
        return [
            {
                'forecast_time': WeatherTransformer._parse_utc_timestamp(
                    timestamp,
                ),
                'fetched_at': fetched_at,
                **WeatherTransformer._extract_fields(
                    hourly,
                    index,
                    ECMWF_HOURLY_FIELDS,
                ),
            }
            for index, timestamp in enumerate(hourly['time'])
        ]

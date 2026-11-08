"""Конфигурация Stormy для локальной разработки и сервера."""

from datetime import date
from functools import lru_cache
from typing import Literal, TypedDict

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConnectionParams(TypedDict):
    """Параметры подключения к PostgreSQL."""

    host: str
    port: int
    user: str
    password: str
    dbname: str


class Settings(BaseSettings):
    """Хранит и проверяет настройки приложения и ETL."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    # Среда выполнения.
    app_env: Literal['local', 'server'] = 'local'

    # PostgreSQL.
    db_host: str = 'localhost'
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_user: str = 'postgres'
    db_password: str = Field(repr=False)
    db_name: str = 'weather_analytics'

    # Open-Meteo API.
    geocoding_url: str = 'https://geocoding-api.open-meteo.com/v1/search'
    forecast_url: str = 'https://api.open-meteo.com/v1/forecast'
    archive_url: str = 'https://archive-api.open-meteo.com/v1/archive'
    ecmwf_url: str
    http_timeout: float = Field(default=15.0, gt=0)

    # Ограничение запросов к Open-Meteo.
    etl_request_delay: float = Field(default=2.0, ge=0)

    # Локальная разработка: фиксированная выборка городов.
    etl_local_cities: tuple[str, ...] = (
        'Moscow',
        'Dubai',
        'Buenos Aires',
        'Ljubljana',
        'Cairo',
    )

    # Короткий исторический период для локальных проверок.
    etl_local_start_date: date = date(2026, 10, 1)
    etl_local_end_date: date = date(2026, 10, 2)

    # Начальная дата полной серверной истории.
    etl_history_start_date: date = date(2016, 11, 1)

    # Telegram.
    telegram_bot_token: SecretStr

    @model_validator(mode='after')
    def validate_etl_settings(self) -> 'Settings':
        """Проверяет согласованность параметров ETL."""
        if self.etl_local_start_date > self.etl_local_end_date:
            raise ValueError('Начало локального периода позже его окончания')

        if not self.etl_local_cities:
            raise ValueError('Список локальных городов не может быть пустым')

        if len({city.casefold() for city in self.etl_local_cities}) != len(
            self.etl_local_cities
        ):
            raise ValueError('Список локальных городов содержит дубликаты')

        return self


@lru_cache
def get_settings() -> Settings:
    """Возвращает кэшированный экземпляр настроек."""
    return Settings()

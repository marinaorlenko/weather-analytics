"""Конфигурация приложения и подключения к PostgreSQL."""

from functools import lru_cache
from typing import TypedDict

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConnectionParams(TypedDict):
    """Параметры подключения к PostgreSQL."""

    host: str
    port: int
    user: str
    password: str
    dbname: str


class Settings(BaseSettings):
    """Хранит и проверяет настройки приложения."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    db_host: str = 'localhost'
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_user: str = 'postgres'
    db_password: str = Field(repr=False)
    db_name: str = 'weather_analytics'

    geocoding_url: str = 'https://geocoding-api.open-meteo.com/v1/search'
    forecast_url: str = 'https://api.open-meteo.com/v1/forecast'
    http_timeout: float = Field(default=15.0, gt=0)
    archive_url: str = 'https://archive-api.open-meteo.com/v1/archive'
    ecmwf_url: str

    telegram_bot_token: SecretStr


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный кэшированный экземпляр настроек."""
    return Settings()

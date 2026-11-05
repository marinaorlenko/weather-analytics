"""Модели географических локаций и текущих погодных условий."""

from datetime import datetime

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Представляет географическую локацию."""

    name: str
    country: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str


class CurrentWeather(BaseModel):
    """Хранит текущие погодные показатели для локации."""

    location: Location
    observed_at: datetime
    temperature: float
    humidity: int = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0)

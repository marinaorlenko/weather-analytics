"""SQLAlchemy-модели существующей схемы PostgreSQL."""

from datetime import date, datetime

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовый класс SQLAlchemy-моделей."""


class City(Base):
    """Справочник городов."""

    __tablename__ = 'cities'
    __table_args__ = (
        UniqueConstraint('name', 'country'),
        CheckConstraint(
            'latitude BETWEEN -90 AND 90',
            name='cities_latitude_check',
        ),
        CheckConstraint(
            'longitude BETWEEN -180 AND 180',
            name='cities_longitude_check',
        ),
    )

    city_id: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(150))
    country: Mapped[str] = mapped_column(String(150))
    latitude: Mapped[float] = mapped_column(Double)
    longitude: Mapped[float] = mapped_column(Double)
    timezone: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text('true'),
    )


class HistoricalDaily(Base):
    """Суточные исторические показатели."""

    __tablename__ = 'historical_daily'
    __table_args__ = (
        PrimaryKeyConstraint('city_id', 'weather_date'),
        Index('idx_historical_daily_date', 'weather_date'),
    )

    city_id: Mapped[int] = mapped_column(Integer, ForeignKey('cities.city_id'))
    weather_date: Mapped[date] = mapped_column(Date)
    weather_code: Mapped[int | None] = mapped_column(SmallInteger)
    temperature_mean: Mapped[float | None] = mapped_column(REAL)
    temperature_min: Mapped[float | None] = mapped_column(REAL)
    temperature_max: Mapped[float | None] = mapped_column(REAL)
    apparent_temperature_mean: Mapped[float | None] = mapped_column(REAL)
    apparent_temperature_min: Mapped[float | None] = mapped_column(REAL)
    apparent_temperature_max: Mapped[float | None] = mapped_column(REAL)
    sunrise: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sunset: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daylight_duration: Mapped[float | None] = mapped_column(REAL)
    sunshine_duration: Mapped[float | None] = mapped_column(REAL)
    precipitation: Mapped[float | None] = mapped_column(REAL)
    rain_sum: Mapped[float | None] = mapped_column(REAL)
    snowfall_sum: Mapped[float | None] = mapped_column(REAL)
    precipitation_hours: Mapped[float | None] = mapped_column(REAL)
    wind_speed_max: Mapped[float | None] = mapped_column(REAL)
    wind_gusts_max: Mapped[float | None] = mapped_column(REAL)
    wind_direction_dominant: Mapped[float | None] = mapped_column(REAL)
    shortwave_radiation_sum: Mapped[float | None] = mapped_column(REAL)
    et0_fao_evapotranspiration: Mapped[float | None] = mapped_column(REAL)
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text('now()'),
    )


class HistoricalHourly(Base):
    """Почасовые исторические показатели."""

    __tablename__ = 'historical_hourly'
    __table_args__ = (
        PrimaryKeyConstraint('city_id', 'weather_time'),
        Index('idx_historical_hourly_time', 'weather_time'),
    )

    city_id: Mapped[int] = mapped_column(Integer, ForeignKey('cities.city_id'))
    weather_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temperature: Mapped[float | None] = mapped_column(REAL)
    humidity: Mapped[int | None] = mapped_column(SmallInteger)
    dew_point: Mapped[float | None] = mapped_column(REAL)
    apparent_temperature: Mapped[float | None] = mapped_column(REAL)
    wet_bulb_temperature: Mapped[float | None] = mapped_column(REAL)
    precipitation: Mapped[float | None] = mapped_column(REAL)
    rain: Mapped[float | None] = mapped_column(REAL)
    snowfall: Mapped[float | None] = mapped_column(REAL)
    snow_depth: Mapped[float | None] = mapped_column(REAL)
    weather_code: Mapped[int | None] = mapped_column(SmallInteger)
    pressure_msl: Mapped[float | None] = mapped_column(REAL)
    surface_pressure: Mapped[float | None] = mapped_column(REAL)
    cloud_cover: Mapped[int | None] = mapped_column(SmallInteger)
    cloud_cover_low: Mapped[int | None] = mapped_column(SmallInteger)
    cloud_cover_mid: Mapped[int | None] = mapped_column(SmallInteger)
    cloud_cover_high: Mapped[int | None] = mapped_column(SmallInteger)
    wind_speed: Mapped[float | None] = mapped_column(REAL)
    wind_direction: Mapped[float | None] = mapped_column(REAL)
    wind_gusts: Mapped[float | None] = mapped_column(REAL)
    shortwave_radiation: Mapped[float | None] = mapped_column(REAL)
    direct_radiation: Mapped[float | None] = mapped_column(REAL)
    diffuse_radiation: Mapped[float | None] = mapped_column(REAL)
    sunshine_duration: Mapped[float | None] = mapped_column(REAL)
    et0_fao_evapotranspiration: Mapped[float | None] = mapped_column(REAL)
    vapour_pressure_deficit: Mapped[float | None] = mapped_column(REAL)
    is_day: Mapped[bool | None] = mapped_column(Boolean)
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text('now()'),
    )


class ETLRun(Base):
    """Журнал запусков ETL."""

    __tablename__ = 'etl_runs'
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'failed')",
            name='etl_runs_status_check',
        ),
        Index(
            'idx_etl_runs_pipeline_started',
            'pipeline',
            text('started_at DESC'),
        ),
    )

    run_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True,
    )
    pipeline: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text('now()'),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'running'"),
    )
    rows_loaded: Mapped[int] = mapped_column(
        Integer, server_default=text('0'),
    )
    error_message: Mapped[str | None] = mapped_column(Text)


class ForecastDaily(Base):
    """Суточные прогнозы с сохранением версий."""

    __tablename__ = 'forecast_daily'
    __table_args__ = (
        PrimaryKeyConstraint('city_id', 'forecast_date', 'fetched_at'),
        Index('idx_forecast_daily_date', 'forecast_date'),
    )

    city_id: Mapped[int] = mapped_column(Integer, ForeignKey('cities.city_id'))
    forecast_date: Mapped[date] = mapped_column(Date)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    forecast_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('etl_runs.run_id'),
    )
    weather_code: Mapped[int | None] = mapped_column(SmallInteger)
    temperature_mean: Mapped[float | None] = mapped_column(REAL)
    temperature_min: Mapped[float | None] = mapped_column(REAL)
    temperature_max: Mapped[float | None] = mapped_column(REAL)
    apparent_temperature_mean: Mapped[float | None] = mapped_column(REAL)
    apparent_temperature_min: Mapped[float | None] = mapped_column(REAL)
    apparent_temperature_max: Mapped[float | None] = mapped_column(REAL)
    sunrise: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sunset: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daylight_duration: Mapped[float | None] = mapped_column(REAL)
    sunshine_duration: Mapped[float | None] = mapped_column(REAL)
    precipitation: Mapped[float | None] = mapped_column(REAL)
    rain_sum: Mapped[float | None] = mapped_column(REAL)
    showers_sum: Mapped[float | None] = mapped_column(REAL)
    snowfall_sum: Mapped[float | None] = mapped_column(REAL)
    precipitation_hours: Mapped[float | None] = mapped_column(REAL)
    precipitation_probability_max: Mapped[float | None] = mapped_column(REAL)
    precipitation_probability_mean: Mapped[float | None] = mapped_column(REAL)
    wind_speed_max: Mapped[float | None] = mapped_column(REAL)
    wind_gusts_max: Mapped[float | None] = mapped_column(REAL)
    wind_direction_dominant: Mapped[float | None] = mapped_column(REAL)
    shortwave_radiation_sum: Mapped[float | None] = mapped_column(REAL)
    uv_index_max: Mapped[float | None] = mapped_column(REAL)
    uv_index_clear_sky_max: Mapped[float | None] = mapped_column(REAL)
    et0_fao_evapotranspiration: Mapped[float | None] = mapped_column(REAL)


class ForecastHourly(Base):
    """Почасовые прогнозы с сохранением версий."""

    __tablename__ = 'forecast_hourly'
    __table_args__ = (
        PrimaryKeyConstraint('city_id', 'forecast_time', 'fetched_at'),
        Index('idx_forecast_hourly_time', 'forecast_time'),
    )

    city_id: Mapped[int] = mapped_column(Integer, ForeignKey('cities.city_id'))
    forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    forecast_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('etl_runs.run_id'),
    )
    temperature: Mapped[float | None] = mapped_column(REAL)
    humidity: Mapped[int | None] = mapped_column(SmallInteger)
    dew_point: Mapped[float | None] = mapped_column(REAL)
    apparent_temperature: Mapped[float | None] = mapped_column(REAL)
    wet_bulb_temperature: Mapped[float | None] = mapped_column(REAL)
    precipitation_probability: Mapped[float | None] = mapped_column(REAL)
    precipitation: Mapped[float | None] = mapped_column(REAL)
    rain: Mapped[float | None] = mapped_column(REAL)
    showers: Mapped[float | None] = mapped_column(REAL)
    snowfall: Mapped[float | None] = mapped_column(REAL)
    snow_depth: Mapped[float | None] = mapped_column(REAL)
    weather_code: Mapped[int | None] = mapped_column(SmallInteger)
    pressure_msl: Mapped[float | None] = mapped_column(REAL)
    surface_pressure: Mapped[float | None] = mapped_column(REAL)
    cloud_cover: Mapped[int | None] = mapped_column(SmallInteger)
    cloud_cover_low: Mapped[int | None] = mapped_column(SmallInteger)
    cloud_cover_mid: Mapped[int | None] = mapped_column(SmallInteger)
    cloud_cover_high: Mapped[int | None] = mapped_column(SmallInteger)
    visibility: Mapped[float | None] = mapped_column(REAL)
    evapotranspiration: Mapped[float | None] = mapped_column(REAL)
    et0_fao_evapotranspiration: Mapped[float | None] = mapped_column(REAL)
    vapour_pressure_deficit: Mapped[float | None] = mapped_column(REAL)
    wind_speed: Mapped[float | None] = mapped_column(REAL)
    wind_direction: Mapped[float | None] = mapped_column(REAL)
    wind_gusts: Mapped[float | None] = mapped_column(REAL)
    shortwave_radiation: Mapped[float | None] = mapped_column(REAL)
    direct_radiation: Mapped[float | None] = mapped_column(REAL)
    diffuse_radiation: Mapped[float | None] = mapped_column(REAL)
    uv_index: Mapped[float | None] = mapped_column(REAL)
    uv_index_clear_sky: Mapped[float | None] = mapped_column(REAL)
    sunshine_duration: Mapped[float | None] = mapped_column(REAL)
    cape: Mapped[float | None] = mapped_column(REAL)
    lifted_index: Mapped[float | None] = mapped_column(REAL)
    convective_inhibition: Mapped[float | None] = mapped_column(REAL)
    freezing_level_height: Mapped[float | None] = mapped_column(REAL)
    is_day: Mapped[bool | None] = mapped_column(Boolean)


class ForecastECMWFHourly(Base):
    """Специализированный почасовой прогноз ECMWF."""

    __tablename__ = 'forecast_ecmwf_hourly'
    __table_args__ = (
        PrimaryKeyConstraint('city_id', 'forecast_time', 'fetched_at'),
        Index('idx_forecast_ecmwf_hourly_time', 'forecast_time'),
    )

    city_id: Mapped[int] = mapped_column(Integer, ForeignKey('cities.city_id'))
    forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    forecast_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('etl_runs.run_id'),
    )
    precipitation_type: Mapped[float | None] = mapped_column(REAL)
    snowfall_water_equivalent: Mapped[float | None] = mapped_column(REAL)
    snow_depth_water_equivalent: Mapped[float | None] = mapped_column(REAL)
    cape: Mapped[float | None] = mapped_column(REAL)
    wet_bulb_temperature: Mapped[float | None] = mapped_column(REAL)
    lightning_density: Mapped[float | None] = mapped_column(REAL)
    convective_inhibition: Mapped[float | None] = mapped_column(REAL)


class ETLState(Base):
    """Состояние загрузки исторических данных."""

    __tablename__ = 'etl_state'
    __table_args__ = (
        PrimaryKeyConstraint('pipeline', 'city_id'),
    )

    pipeline: Mapped[str] = mapped_column(String(100))
    city_id: Mapped[int] = mapped_column(Integer, ForeignKey('cities.city_id'))
    last_loaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    last_loaded_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text('now()'),
    )

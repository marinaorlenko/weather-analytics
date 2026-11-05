-- ============================================================
-- СПРАВОЧНИК ГОРОДОВ
-- ============================================================

CREATE TABLE IF NOT EXISTS cities (
    city_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    country VARCHAR(150) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    timezone VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE (name, country),

    CONSTRAINT cities_latitude_check
        CHECK (latitude BETWEEN -90 AND 90),

    CONSTRAINT cities_longitude_check
        CHECK (longitude BETWEEN -180 AND 180)
);


-- ============================================================
-- ИСТОРИЧЕСКИЕ ДАННЫЕ: СУТОЧНЫЕ ПОКАЗАТЕЛИ
-- Источник: Open-Meteo Historical Weather API
-- ============================================================

CREATE TABLE IF NOT EXISTS historical_daily (
    city_id INTEGER NOT NULL REFERENCES cities(city_id),
    weather_date DATE NOT NULL,

    -- Код погодного явления WMO.
    weather_code SMALLINT,

    -- Температура воздуха, °C.
    temperature_mean REAL,
    temperature_min REAL,
    temperature_max REAL,

    -- Ощущаемая температура, °C.
    apparent_temperature_mean REAL,
    apparent_temperature_min REAL,
    apparent_temperature_max REAL,

    -- Солнце и продолжительность дня.
    sunrise TIMESTAMPTZ,
    sunset TIMESTAMPTZ,
    daylight_duration REAL,
    sunshine_duration REAL,

    -- Осадки.
    precipitation REAL,
    rain_sum REAL,
    snowfall_sum REAL,
    precipitation_hours REAL,

    -- Ветер.
    wind_speed_max REAL,
    wind_gusts_max REAL,
    wind_direction_dominant REAL,

    -- Солнечная радиация и испарение.
    shortwave_radiation_sum REAL,
    et0_fao_evapotranspiration REAL,

    -- Время загрузки исторических данных.
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (city_id, weather_date)
);


-- ============================================================
-- ИСТОРИЧЕСКИЕ ДАННЫЕ: ПОЧАСОВЫЕ ПОКАЗАТЕЛИ
-- Источник: Open-Meteo Historical Weather API
-- ============================================================

CREATE TABLE IF NOT EXISTS historical_hourly (
    city_id INTEGER NOT NULL REFERENCES cities(city_id),
    weather_time TIMESTAMPTZ NOT NULL,

    -- Температура и влажность.
    temperature REAL,
    humidity SMALLINT,
    dew_point REAL,
    apparent_temperature REAL,
    wet_bulb_temperature REAL,

    -- Осадки и снег.
    precipitation REAL,
    rain REAL,
    snowfall REAL,
    snow_depth REAL,
    weather_code SMALLINT,

    -- Атмосферное давление.
    pressure_msl REAL,
    surface_pressure REAL,

    -- Облачность.
    cloud_cover SMALLINT,
    cloud_cover_low SMALLINT,
    cloud_cover_mid SMALLINT,
    cloud_cover_high SMALLINT,

    -- Ветер.
    wind_speed REAL,
    wind_direction REAL,
    wind_gusts REAL,

    -- Солнечная радиация.
    shortwave_radiation REAL,
    direct_radiation REAL,
    diffuse_radiation REAL,
    sunshine_duration REAL,

    -- Испарение и дефицит давления водяного пара.
    et0_fao_evapotranspiration REAL,
    vapour_pressure_deficit REAL,

    -- Признак дневного времени.
    is_day BOOLEAN,

    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (city_id, weather_time)
);


-- ============================================================
-- ЖУРНАЛ ЗАПУСКОВ ETL
-- ============================================================

CREATE TABLE IF NOT EXISTS etl_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,

    CONSTRAINT etl_runs_status_check
        CHECK (status IN ('running', 'success', 'failed'))
);


-- ============================================================
-- ПРОГНОЗ: СУТОЧНЫЕ ПОКАЗАТЕЛИ
-- Источник: Open-Meteo Forecast API
-- Каждая загрузка сохраняется как отдельная версия прогноза.
-- ============================================================

CREATE TABLE IF NOT EXISTS forecast_daily (
    city_id INTEGER NOT NULL REFERENCES cities(city_id),
    forecast_date DATE NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    forecast_run_id BIGINT REFERENCES etl_runs(run_id),

    -- Код погодного явления WMO.
    weather_code SMALLINT,

    -- Температура воздуха, °C.
    temperature_mean REAL,
    temperature_min REAL,
    temperature_max REAL,

    -- Ощущаемая температура, °C.
    apparent_temperature_mean REAL,
    apparent_temperature_min REAL,
    apparent_temperature_max REAL,

    -- Солнце и продолжительность дня.
    sunrise TIMESTAMPTZ,
    sunset TIMESTAMPTZ,
    daylight_duration REAL,
    sunshine_duration REAL,

    -- Осадки.
    precipitation REAL,
    rain_sum REAL,
    showers_sum REAL,
    snowfall_sum REAL,
    precipitation_hours REAL,
    precipitation_probability_max REAL,
    precipitation_probability_mean REAL,

    -- Ветер.
    wind_speed_max REAL,
    wind_gusts_max REAL,
    wind_direction_dominant REAL,

    -- Радиация, УФ-индекс и испарение.
    shortwave_radiation_sum REAL,
    uv_index_max REAL,
    uv_index_clear_sky_max REAL,
    et0_fao_evapotranspiration REAL,

    PRIMARY KEY (city_id, forecast_date, fetched_at)
);


-- ============================================================
-- ПРОГНОЗ: ПОЧАСОВЫЕ ПОКАЗАТЕЛИ
-- Источник: Open-Meteo Forecast API
-- ============================================================

CREATE TABLE IF NOT EXISTS forecast_hourly (
    city_id INTEGER NOT NULL REFERENCES cities(city_id),
    forecast_time TIMESTAMPTZ NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    forecast_run_id BIGINT REFERENCES etl_runs(run_id),

    -- Температура и влажность.
    temperature REAL,
    humidity SMALLINT,
    dew_point REAL,
    apparent_temperature REAL,
    wet_bulb_temperature REAL,

    -- Осадки и снег.
    precipitation_probability REAL,
    precipitation REAL,
    rain REAL,
    showers REAL,
    snowfall REAL,
    snow_depth REAL,
    weather_code SMALLINT,

    -- Атмосферное давление.
    pressure_msl REAL,
    surface_pressure REAL,

    -- Облачность.
    cloud_cover SMALLINT,
    cloud_cover_low SMALLINT,
    cloud_cover_mid SMALLINT,
    cloud_cover_high SMALLINT,

    -- Видимость.
    visibility REAL,

    -- Испарение.
    evapotranspiration REAL,
    et0_fao_evapotranspiration REAL,
    vapour_pressure_deficit REAL,

    -- Ветер.
    wind_speed REAL,
    wind_direction REAL,
    wind_gusts REAL,

    -- Солнечная радиация.
    shortwave_radiation REAL,
    direct_radiation REAL,
    diffuse_radiation REAL,

    -- Ультрафиолетовое излучение.
    uv_index REAL,
    uv_index_clear_sky REAL,

    -- Продолжительность солнечного сияния.
    sunshine_duration REAL,

    -- Показатели конвективной активности.
    cape REAL,
    lifted_index REAL,
    convective_inhibition REAL,
    freezing_level_height REAL,

    -- Признак дневного времени.
    is_day BOOLEAN,

    PRIMARY KEY (city_id, forecast_time, fetched_at)
);


-- ============================================================
-- СПЕЦИАЛИЗИРОВАННЫЙ ПОЧАСОВОЙ ПРОГНОЗ ECMWF
-- Источник: Open-Meteo ECMWF API
-- Не смешиваем значения с основным прогнозом.
-- ============================================================

CREATE TABLE IF NOT EXISTS forecast_ecmwf_hourly (
    city_id INTEGER NOT NULL REFERENCES cities(city_id),
    forecast_time TIMESTAMPTZ NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    forecast_run_id BIGINT REFERENCES etl_runs(run_id),

    -- Классификация типа осадков ECMWF.
    precipitation_type REAL,

    -- Снег в водном эквиваленте.
    snowfall_water_equivalent REAL,
    snow_depth_water_equivalent REAL,

    -- Конвективная активность.
    cape REAL,

    -- Температура влажного термометра.
    wet_bulb_temperature REAL,

    -- Пока недоступные показатели оставляем NULL.
    -- Они могут стать доступны для других моделей и регионов.
    lightning_density REAL,
    convective_inhibition REAL,

    PRIMARY KEY (city_id, forecast_time, fetched_at)
);


-- ============================================================
-- СОСТОЯНИЕ ЗАГРУЗКИ ETL
-- Позволяет продолжать загрузку исторических данных.
-- ============================================================

CREATE TABLE IF NOT EXISTS etl_state (
    pipeline VARCHAR(100) NOT NULL,
    city_id INTEGER NOT NULL REFERENCES cities(city_id),
    last_loaded_at TIMESTAMPTZ,
    last_loaded_date DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (pipeline, city_id)
);


-- ============================================================
-- ИНДЕКСЫ ДЛЯ АНАЛИТИЧЕСКИХ ЗАПРОСОВ
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_historical_daily_date
    ON historical_daily (weather_date);

CREATE INDEX IF NOT EXISTS idx_historical_hourly_time
    ON historical_hourly (weather_time);

CREATE INDEX IF NOT EXISTS idx_forecast_daily_date
    ON forecast_daily (forecast_date);

CREATE INDEX IF NOT EXISTS idx_forecast_hourly_time
    ON forecast_hourly (forecast_time);

CREATE INDEX IF NOT EXISTS idx_forecast_ecmwf_hourly_time
    ON forecast_ecmwf_hourly (forecast_time);

CREATE INDEX IF NOT EXISTS idx_etl_runs_pipeline_started
    ON etl_runs (pipeline, started_at DESC);

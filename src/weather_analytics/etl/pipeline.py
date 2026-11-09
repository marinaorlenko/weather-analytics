"""Оркестрация исторической и прогнозной загрузки Stormy.

Модуль управляет выбором городов, инициализацией PostgreSQL,
загрузкой погодных данных, проверкой и сохранением результатов.

История загружается по календарным месяцам с возможностью
возобновления. Режим batch ограничивает объём одного запуска.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from weather_analytics.api import OpenMeteoClient
from weather_analytics.db.initializer import DatabaseInitializer
from weather_analytics.etl.city_reader import CityReader
from weather_analytics.etl.date_utils import split_date_range
from weather_analytics.etl.extractor import WeatherExtractor
from weather_analytics.etl.loader import WeatherLoader
from weather_analytics.etl.transformer import WeatherTransformer
from weather_analytics.etl.validator import validate_historical_records
from weather_analytics.models.weather import Location

logger = logging.getLogger(__name__)

ETLMode = Literal['local', 'initial', 'daily', 'forecast', 'batch']


class WeatherETL:
    """Управляет исторической и прогнозной загрузкой данных."""

    def run(
        self,
        mode: ETLMode = 'local',
        city_names: tuple[str, ...] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        max_periods: int | None = None,
    ) -> None:
        """Запускает ETL с необязательным общим лимитом периодов."""
        if mode not in ('local', 'initial', 'daily', 'forecast', 'batch'):
            raise ValueError(f'Неизвестный режим ETL: {mode}')

        if mode != 'forecast':
            if start_date is None or end_date is None:
                raise ValueError(
                    'Для исторической загрузки необходимо '
                    'указать начальную и конечную даты'
                )

            if start_date > end_date:
                raise ValueError('Начальная дата не может быть позже конечной')

        if max_periods is not None and max_periods < 1:
            raise ValueError('Лимит периодов должен быть положительным')

        initializer = DatabaseInitializer()
        initializer.initialize()

        loader = WeatherLoader()
        transformer = WeatherTransformer()

        locations = CityReader('data/capitals.csv').read()

        # Выборка городов определяется названиями из справочника.
        if city_names is not None:
            selected = {name.casefold() for name in city_names}
            available = {location.name.casefold() for location in locations}
            missing = selected - available

            if missing:
                raise ValueError(
                    'В справочнике отсутствуют города: ' + ', '.join(sorted(missing))
                )

            locations = [
                location
                for location in locations
                if location.name.casefold() in selected
            ]

        logger.info(
            'Запуск ETL: режим=%s, городов=%s, период=%s — %s, лимит=%s',
            mode,
            len(locations),
            start_date,
            end_date,
            max_periods,
        )

        successful = 0
        failed = 0
        processed_periods = 0

        for location in locations:
            # Лимит общий для всех городов.
            if max_periods is not None and processed_periods >= max_periods:
                logger.info('Достигнут лимит: %s периодов', max_periods)
                break

            try:
                city_id = loader.save_city(location)
            except Exception:
                failed += 1
                logger.exception('Ошибка сохранения города: %s', location.name)
                continue

            city_success = True

            if mode in ('local', 'initial', 'daily', 'batch'):
                try:
                    remaining = (
                        None if max_periods is None else max_periods - processed_periods
                    )

                    if remaining is None:
                        # Сохраняем прежний вызов для существующих режимов ETL.
                        result = self._run_historical(
                            loader,
                            transformer,
                            location,
                            city_id,
                            start_date,
                            end_date,
                        )
                    else:
                        # В режиме batch передаём ограничение периодов.
                        result = self._run_historical(
                            loader,
                            transformer,
                            location,
                            city_id,
                            start_date,
                            end_date,
                            remaining,
                        )

                    if result is not None:
                        processed_periods += result
                except Exception:
                    city_success = False
                    logger.exception(
                        'Ошибка исторического ETL: %s',
                        location.name,
                    )

            if mode in ('local', 'forecast'):
                try:
                    self._run_forecast(
                        loader,
                        transformer,
                        location,
                        city_id,
                    )
                except Exception:
                    city_success = False
                    logger.exception(
                        'Ошибка прогнозного ETL: %s',
                        location.name,
                    )

            if city_success:
                successful += 1
            else:
                failed += 1

        logger.info(
            'ETL завершён: успешно=%s, ошибок=%s, периодов=%s',
            successful,
            failed,
            processed_periods,
        )

        if failed:
            raise RuntimeError(f'ETL завершён с ошибками для {failed} городов')

    def _run_historical(
        self,
        loader: WeatherLoader,
        transformer: WeatherTransformer,
        location: Location,
        city_id: int,
        start_date: date,
        end_date: date,
        max_periods: int | None = None,
    ) -> int:
        """Загружает историю и возвращает число сохранённых периодов."""
        last_loaded_date = loader.get_last_loaded_date(city_id)

        if last_loaded_date is not None:
            start_date = max(
                start_date,
                last_loaded_date + timedelta(days=1),
            )

        if start_date > end_date:
            logger.info(
                'История города %s уже загружена до %s',
                location.name,
                end_date,
            )
            return 0

        periods = split_date_range(start_date, end_date)
        processed = 0

        for period_start, period_end in periods:
            if max_periods is not None and processed >= max_periods:
                break

            run_id = loader.start_run('historical')

            try:
                with OpenMeteoClient() as client:
                    extractor = WeatherExtractor(client)
                    data = extractor.extract_historical(
                        location,
                        period_start,
                        period_end,
                    )

                daily_records = transformer.transform_historical_daily(
                    location,
                    {'daily': data['daily']},
                )

                hourly_records = transformer.transform_historical_hourly(
                    location,
                    {'hourly': data['hourly']},
                )

                validate_historical_records(
                    location,
                    period_start,
                    period_end,
                    daily_records,
                    hourly_records,
                )

                rows_loaded = loader.save_historical_period(
                    city_id=city_id,
                    run_id=run_id,
                    daily_records=daily_records,
                    hourly_records=hourly_records,
                    loaded_date=period_end,
                )

                processed += 1

                logger.info(
                    'История: %s, %s — %s, записей=%s',
                    location.name,
                    period_start,
                    period_end,
                    rows_loaded,
                )

            except Exception as error:
                try:
                    loader.fail_run(run_id, error)
                except Exception:
                    logger.exception(
                        'Ошибка регистрации сбоя ETL: run_id=%s',
                        run_id,
                    )

                raise

        return processed

    def _run_forecast(
        self,
        loader: WeatherLoader,
        transformer: WeatherTransformer,
        location: Location,
        city_id: int,
    ) -> None:
        """Загружает основной прогноз и ECMWF единым снимком."""
        run_id = loader.start_run('forecast')

        try:
            fetched_at = datetime.now(UTC)

            with OpenMeteoClient() as client:
                extractor = WeatherExtractor(client)
                data = extractor.extract_forecast(location)

            daily_records = transformer.transform_forecast_daily(
                location,
                {'daily': data['daily']},
                fetched_at,
            )

            hourly_records = transformer.transform_forecast_hourly(
                location,
                {'hourly': data['hourly']},
                fetched_at,
            )

            ecmwf_records = transformer.transform_ecmwf_hourly(
                location,
                {'hourly': data['ecmwf_hourly']},
                fetched_at,
            )

            rows_loaded = loader.save_forecast_snapshot(
                city_id=city_id,
                run_id=run_id,
                daily_records=daily_records,
                hourly_records=hourly_records,
                ecmwf_records=ecmwf_records,
            )

            logger.info(
                'Прогноз: %s, fetched_at=%s, записей=%s',
                location.name,
                fetched_at.isoformat(),
                rows_loaded,
            )

        except Exception as error:
            try:
                loader.fail_run(run_id, error)
            except Exception:
                logger.exception(
                    'Ошибка регистрации сбоя прогноза: run_id=%s',
                    run_id,
                )

            raise

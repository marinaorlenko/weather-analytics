"""Оркестрация загрузки исторических и прогнозных погодных данных.

Модуль управляет последовательностью ETL-операций:
чтением городов, извлечением данных, преобразованием,
проверкой и сохранением в PostgreSQL.

Исторические данные загружаются по периодам с возможностью
возобновления. Прогнозные данные сохраняются единым снимком.
"""

import logging
from datetime import UTC, date, datetime, timedelta

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


class WeatherETL:
    """Управляет исторической и прогнозной загрузкой погодных данных."""

    def run(
        self,
        city_limit: int = 3,
        start_date: date = date(2026, 10, 1),
        end_date: date = date(2026, 10, 2),
    ) -> None:
        """Запускает ETL для заданного количества городов и периода.

        Args:
            city_limit: Максимальное количество обрабатываемых городов.
            start_date: Начало исторического периода.
            end_date: Конец исторического периода.

        Raises:
            ValueError: Если параметры загрузки некорректны.
        """
        # Проверяем входные параметры до подключения к базе
        # и выполнения запросов к внешнему API.
        if city_limit < 1:
            raise ValueError(
                'Количество городов должно быть положительным'
            )

        if start_date > end_date:
            raise ValueError(
                'Начальная дата не может быть позже конечной'
            )

        # Создаём базу данных при необходимости
        # и инициализируем компоненты ETL.
        initializer = DatabaseInitializer()
        initializer.initialize()

        loader = WeatherLoader()
        transformer = WeatherTransformer()

        # Читаем справочник столиц и ограничиваем выборку.
        locations = CityReader('data/capitals.csv').read()[:city_limit]

        successful = 0
        failed = 0

        logger.info(
            'Начало загрузки: городов=%s, период=%s — %s',
            len(locations),
            start_date,
            end_date,
        )

        for location in locations:
            # Ошибка сохранения отдельного города
            # не должна останавливать обработку остальных.
            try:
                city_id = loader.save_city(location)
            except Exception:
                failed += 1
                logger.exception(
                    'Не удалось сохранить город: %s',
                    location.name,
                )
                continue

            city_success = True

            # Историческая загрузка выполняется независимо
            # от прогнозной, чтобы сбой одной не блокировал другую.
            try:
                self._run_historical(
                    loader,
                    transformer,
                    location,
                    city_id,
                    start_date,
                    end_date,
                )
            except Exception:
                city_success = False
                logger.exception(
                    'Ошибка исторической загрузки: %s',
                    location.name,
                )

            # Прогнозный снимок объединяет основной прогноз
            # и специализированные показатели ECMWF.
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
                    'Ошибка прогнозной загрузки: %s',
                    location.name,
                )

            if city_success:
                successful += 1
            else:
                failed += 1

        logger.info(
            'Загрузка завершена: успешно=%s, с ошибками=%s, всего=%s',
            successful,
            failed,
            len(locations),
        )

    def _run_historical(
        self,
        loader: WeatherLoader,
        transformer: WeatherTransformer,
        location: Location,
        city_id: int,
        start_date: date,
        end_date: date,
    ) -> None:
        """Загружает исторические данные с поддержкой возобновления.

        Args:
            loader: Компонент сохранения данных в PostgreSQL.
            transformer: Компонент преобразования ответов API.
            location: Обрабатываемая географическая локация.
            city_id: Идентификатор города в базе данных.
            start_date: Начало запрошенного периода.
            end_date: Конец запрошенного периода.
        """
        # Определяем последнюю успешно загруженную дату.
        # Уже завершённые периоды повторно не запрашиваем.
        last_loaded_date = loader.get_last_loaded_date(city_id)

        if last_loaded_date is not None:
            start_date = max(
                start_date,
                last_loaded_date + timedelta(days=1),
            )

        if start_date > end_date:
            logger.info(
                'Историческая загрузка не требуется: %s, '
                'данные уже загружены',
                location.name,
            )
            return

        # Разбиваем диапазон на отдельные интервалы.
        # Каждый интервал обрабатывается самостоятельно.
        periods = split_date_range(start_date, end_date)

        for period_start, period_end in periods:
            run_id = loader.start_run('historical')

            try:
                # Извлекаем суточные и почасовые данные
                # через единый публичный клиент Open-Meteo.
                with OpenMeteoClient() as client:
                    extractor = WeatherExtractor(client)
                    data = extractor.extract_historical(
                        location,
                        period_start,
                        period_end,
                    )

                # Преобразуем ответы API в записи,
                # соответствующие структуре таблиц PostgreSQL.
                daily_records = transformer.transform_historical_daily(
                    location,
                    {'daily': data['daily']},
                )

                hourly_records = transformer.transform_historical_hourly(
                    location,
                    {'hourly': data['hourly']},
                )

                # Проверяем полноту исторических данных
                # до начала транзакционного сохранения.
                validate_historical_records(
                    location,
                    period_start,
                    period_end,
                    daily_records,
                    hourly_records,
                )

                # Данные, прогресс и статус ETL-запуска
                # сохраняются одной транзакцией.
                rows_loaded = loader.save_historical_period(
                    city_id=city_id,
                    run_id=run_id,
                    daily_records=daily_records,
                    hourly_records=hourly_records,
                    loaded_date=period_end,
                )

                logger.info(
                    'Исторический ETL завершён: %s, период %s — %s, '
                    'ежедневных=%s, почасовых=%s, всего=%s',
                    location.name,
                    period_start,
                    period_end,
                    len(daily_records),
                    len(hourly_records),
                    rows_loaded,
                )

            except Exception as error:
                # Ошибку регистрируем отдельно от транзакции
                # загрузки, которая могла быть отменена.
                try:
                    loader.fail_run(run_id, error)
                except Exception:
                    logger.exception(
                        'Не удалось зарегистрировать ошибку '
                        'исторического ETL: run_id=%s',
                        run_id,
                    )

                raise

    def _run_forecast(
        self,
        loader: WeatherLoader,
        transformer: WeatherTransformer,
        location: Location,
        city_id: int,
    ) -> None:
        """Загружает основной прогноз и ECMWF единым снимком.

        Args:
            loader: Компонент сохранения данных в PostgreSQL.
            transformer: Компонент преобразования ответов API.
            location: Обрабатываемая географическая локация.
            city_id: Идентификатор города в базе данных.
        """
        run_id = loader.start_run('forecast')

        try:
            # Используем единое время получения снимка
            # для всех прогнозных таблиц.
            fetched_at = datetime.now(UTC)

            # Получаем суточный, почасовой и ECMWF-прогнозы.
            with OpenMeteoClient() as client:
                extractor = WeatherExtractor(client)
                data = extractor.extract_forecast(location)

            # Преобразуем суточные показатели прогноза.
            daily_records = transformer.transform_forecast_daily(
                location,
                {'daily': data['daily']},
                fetched_at,
            )

            # Преобразуем почасовые показатели прогноза.
            hourly_records = transformer.transform_forecast_hourly(
                location,
                {'hourly': data['hourly']},
                fetched_at,
            )

            # Преобразуем специализированные показатели ECMWF.
            ecmwf_records = transformer.transform_ecmwf_hourly(
                location,
                {'hourly': data['ecmwf_hourly']},
                fetched_at,
            )

            # Все прогнозные таблицы и статус ETL-запуска
            # обновляются одной транзакцией.
            rows_loaded = loader.save_forecast_snapshot(
                city_id=city_id,
                run_id=run_id,
                daily_records=daily_records,
                hourly_records=hourly_records,
                ecmwf_records=ecmwf_records,
            )

            logger.info(
                'Прогнозный ETL завершён: %s, fetched_at=%s, '
                'ежедневных=%s, почасовых=%s, ECMWF=%s, всего=%s',
                location.name,
                fetched_at.isoformat(),
                len(daily_records),
                len(hourly_records),
                len(ecmwf_records),
                rows_loaded,
            )

        except Exception as error:
            # При сбое сохранения Loader откатывает транзакцию.
            # Неудачный ETL-запуск регистрируем отдельно.
            try:
                loader.fail_run(run_id, error)
            except Exception:
                logger.exception(
                    'Не удалось зарегистрировать ошибку '
                    'прогнозного ETL: run_id=%s',
                    run_id,
                )

            raise

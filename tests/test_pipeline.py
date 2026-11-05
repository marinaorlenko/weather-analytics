
"""Тесты общей оркестрации ETL и загрузки прогнозов.

Внешние зависимости подменяются имитациями без обращения к API и PostgreSQL.
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from weather_analytics.etl.pipeline import WeatherETL
from weather_analytics.models.weather import Location

PIPELINE_MODULE = 'weather_analytics.etl.pipeline'


@pytest.fixture
def locations() -> list[Location]:
    """Создаёт тестовые географические локации."""
    return [
        Location(
            name='Dubai',
            country='United Arab Emirates',
            latitude=25.07725,
            longitude=55.30927,
            timezone='Asia/Dubai',
        ),
        Location(
            name='London',
            country='United Kingdom',
            latitude=51.5085,
            longitude=-0.1257,
            timezone='Europe/London',
        ),
        Location(
            name='Paris',
            country='France',
            latitude=48.8534,
            longitude=2.3488,
            timezone='Europe/Paris',
        ),
    ]


@pytest.fixture
def etl() -> WeatherETL:
    """Создаёт оркестратор ETL."""
    return WeatherETL()


@pytest.fixture
def dependencies(locations):
    """Подменяет зависимости общего запуска ETL."""
    with (
        patch(f'{PIPELINE_MODULE}.DatabaseInitializer') as initializer,
        patch(f'{PIPELINE_MODULE}.WeatherLoader') as loader_class,
        patch(f'{PIPELINE_MODULE}.WeatherTransformer') as transformer_class,
        patch(f'{PIPELINE_MODULE}.CityReader') as reader,
    ):
        loader = loader_class.return_value
        reader.return_value.read.return_value = locations
        loader.save_city.side_effect = [1, 2, 3]

        yield {
            'initializer': initializer,
            'loader': loader,
            'transformer': transformer_class.return_value,
            'reader': reader,
        }


@pytest.fixture
def forecast_dependencies():
    """Подменяет клиент API и компонент извлечения прогнозов."""
    with (
        patch(f'{PIPELINE_MODULE}.OpenMeteoClient'),
        patch(f'{PIPELINE_MODULE}.WeatherExtractor') as extractor_class,
    ):
        extractor = extractor_class.return_value
        extractor.extract_forecast.return_value = {
            'daily': {'time': ['2026-10-30']},
            'hourly': {'time': [1793347200]},
            'ecmwf_hourly': {'time': [1793347200]},
        }

        yield extractor


@pytest.mark.parametrize('city_limit', [0, -1])
def test_run_invalid_city_limit(etl, city_limit) -> None:
    """Проверяет отказ от неположительного количества городов."""
    with patch(f'{PIPELINE_MODULE}.DatabaseInitializer') as initializer:
        with pytest.raises(
            ValueError,
            match='Количество городов должно быть положительным',
        ):
            etl.run(city_limit=city_limit)

    initializer.assert_not_called()


def test_run_invalid_date_range(etl) -> None:
    """Проверяет отказ от обратного диапазона дат."""
    with patch(f'{PIPELINE_MODULE}.DatabaseInitializer') as initializer:
        with pytest.raises(
            ValueError,
            match='Начальная дата не может быть позже конечной',
        ):
            etl.run(
                start_date=date(2026, 10, 5),
                end_date=date(2026, 10, 1),
            )

    initializer.assert_not_called()


def test_run_initializes_database(etl, dependencies) -> None:
    """Проверяет инициализацию БД и чтение справочника городов."""
    with (
        patch.object(etl, '_run_historical'),
        patch.object(etl, '_run_forecast'),
    ):
        etl.run(city_limit=1)

    dependencies['initializer'].return_value.initialize.assert_called_once_with()
    dependencies['reader'].assert_called_once_with('data/capitals.csv')


def test_run_respects_city_limit(etl, dependencies, locations) -> None:
    """Проверяет ограничение количества обрабатываемых городов."""
    with (
        patch.object(etl, '_run_historical') as historical,
        patch.object(etl, '_run_forecast') as forecast,
    ):
        etl.run(city_limit=2)

    assert dependencies['loader'].save_city.call_count == 2
    assert historical.call_count == 2
    assert forecast.call_count == 2

    assert [
        item.args[2]
        for item in historical.call_args_list
    ] == locations[:2]


def test_run_calls_both_pipelines(etl, dependencies, locations) -> None:
    """Проверяет запуск истории и прогноза для одного города."""
    with (
        patch.object(etl, '_run_historical') as historical,
        patch.object(etl, '_run_forecast') as forecast,
    ):
        etl.run(
            city_limit=1,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
        )

    loader = dependencies['loader']
    transformer = dependencies['transformer']

    historical.assert_called_once_with(
        loader,
        transformer,
        locations[0],
        1,
        date(2026, 10, 1),
        date(2026, 10, 2),
    )
    forecast.assert_called_once_with(
        loader,
        transformer,
        locations[0],
        1,
    )


def test_run_city_save_failure_does_not_stop_other_cities(
    etl,
    dependencies,
) -> None:
    """Проверяет продолжение обработки после ошибки сохранения города."""
    loader = dependencies['loader']
    loader.save_city.side_effect = [
        RuntimeError('Ошибка сохранения города'),
        2,
    ]

    with (
        patch.object(etl, '_run_historical') as historical,
        patch.object(etl, '_run_forecast') as forecast,
    ):
        etl.run(city_limit=2)

    assert loader.save_city.call_count == 2
    assert historical.call_count == 1
    assert forecast.call_count == 1
    assert historical.call_args.args[3] == 2
    assert forecast.call_args.args[3] == 2


def test_run_historical_failure_does_not_block_forecast(
    etl,
    dependencies,
) -> None:
    """Проверяет независимость прогноза от ошибки исторического ETL."""
    with (
        patch.object(
            etl,
            '_run_historical',
            side_effect=RuntimeError('Ошибка истории'),
        ) as historical,
        patch.object(etl, '_run_forecast') as forecast,
    ):
        etl.run(city_limit=1)

    historical.assert_called_once()
    forecast.assert_called_once()


def test_run_forecast_failure_does_not_block_next_city(
    etl,
    dependencies,
) -> None:
    """Проверяет продолжение ETL после ошибки прогноза."""
    with (
        patch.object(etl, '_run_historical') as historical,
        patch.object(
            etl,
            '_run_forecast',
            side_effect=[
                RuntimeError('Ошибка прогноза'),
                None,
            ],
        ) as forecast,
    ):
        etl.run(city_limit=2)

    assert historical.call_count == 2
    assert forecast.call_count == 2


def test_forecast_saves_single_snapshot(
    etl,
    locations,
    forecast_dependencies,
) -> None:
    """Проверяет сохранение трёх прогнозов единым снимком."""
    loader = MagicMock()
    transformer = MagicMock()

    loader.start_run.return_value = 202

    daily_records = [{'forecast_date': date(2026, 10, 30)}]
    hourly_records = [{'forecast_time': '2026-10-30T00:00:00+00:00'}]
    ecmwf_records = [{'precipitation_type': 1}]

    transformer.transform_forecast_daily.return_value = daily_records
    transformer.transform_forecast_hourly.return_value = hourly_records
    transformer.transform_ecmwf_hourly.return_value = ecmwf_records

    etl._run_forecast(
        loader,
        transformer,
        locations[0],
        1,
    )

    loader.start_run.assert_called_once_with('forecast')

    # Период прогноза задаётся внутри компонента извлечения данных.
    forecast_dependencies.extract_forecast.assert_called_once_with(
        locations[0],
    )

    daily_call = transformer.transform_forecast_daily.call_args
    hourly_call = transformer.transform_forecast_hourly.call_args
    ecmwf_call = transformer.transform_ecmwf_hourly.call_args

    # Все три преобразования должны использовать одно время снимка.
    fetched_at = daily_call.args[2]

    assert isinstance(fetched_at, datetime)
    assert fetched_at.tzinfo is not None
    assert fetched_at.utcoffset() == timedelta(0)
    assert hourly_call.args[2] is fetched_at
    assert ecmwf_call.args[2] is fetched_at

    loader.save_forecast_snapshot.assert_called_once_with(
        city_id=1,
        run_id=202,
        daily_records=daily_records,
        hourly_records=hourly_records,
        ecmwf_records=ecmwf_records,
    )


@pytest.mark.parametrize(
    ('failure_stage', 'message'),
    [
        ('extract', 'Open-Meteo недоступен'),
        ('save', 'Ошибка сохранения прогноза'),
    ],
)
def test_forecast_failure(
    etl,
    locations,
    forecast_dependencies,
    failure_stage,
    message,
) -> None:
    """Проверяет регистрацию ошибки получения или сохранения прогноза."""
    loader = MagicMock()
    transformer = MagicMock()

    loader.start_run.return_value = 202

    if failure_stage == 'extract':
        forecast_dependencies.extract_forecast.side_effect = RuntimeError(
            message,
        )
    else:
        loader.save_forecast_snapshot.side_effect = RuntimeError(message)

    with pytest.raises(RuntimeError, match=message):
        etl._run_forecast(
            loader,
            transformer,
            locations[0],
            1,
        )

    loader.fail_run.assert_called_once()
    assert loader.fail_run.call_args.args[0] == 202

    if failure_stage == 'extract':
        loader.save_forecast_snapshot.assert_not_called()
    else:
        loader.save_forecast_snapshot.assert_called_once()


@pytest.mark.parametrize('pipeline', ['historical', 'forecast'])
def test_fail_run_error_preserves_original(
    etl,
    locations,
    pipeline,
) -> None:
    """Проверяет сохранение исходной ошибки при сбое журнала ETL."""
    loader = MagicMock()
    transformer = MagicMock()

    loader.start_run.return_value = 101
    loader.fail_run.side_effect = RuntimeError('Ошибка журнала')

    # Историческая загрузка начинается без ранее сохранённой даты.
    # Это предотвращает сравнение MagicMock с datetime.date.
    loader.get_last_loaded_date.return_value = None

    with (
        patch(f'{PIPELINE_MODULE}.OpenMeteoClient'),
        patch(f'{PIPELINE_MODULE}.WeatherExtractor') as extractor_class,
    ):
        extractor = extractor_class.return_value

        if pipeline == 'historical':
            extractor.extract_historical.side_effect = ValueError(
                'Ошибка исторического API',
            )
            expected_message = 'Ошибка исторического API'

            with patch(
                f'{PIPELINE_MODULE}.split_date_range',
                return_value=[
                    (date(2026, 10, 1), date(2026, 10, 2)),
                ],
            ):
                with pytest.raises(ValueError, match=expected_message):
                    etl._run_historical(
                        loader,
                        transformer,
                        locations[0],
                        1,
                        date(2026, 10, 1),
                        date(2026, 10, 2),
                    )
        else:
            extractor.extract_forecast.side_effect = ValueError(
                'Некорректный ответ API',
            )
            expected_message = 'Некорректный ответ API'

            with pytest.raises(ValueError, match=expected_message):
                etl._run_forecast(
                    loader,
                    transformer,
                    locations[0],
                    1,
                )

    loader.fail_run.assert_called_once()

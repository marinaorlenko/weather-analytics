
"""Тесты помесячной загрузки и возобновления исторического ETL."""

from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest

from weather_analytics.etl.pipeline import WeatherETL
from weather_analytics.etl.validator import validate_historical_records
from weather_analytics.models.weather import Location


@pytest.fixture
def location() -> Location:
    """Создаёт тестовую локацию."""
    return Location(
        name='Kabul',
        country='Afghanistan',
        latitude=34.526011,
        longitude=69.177684,
        timezone='Asia/Kabul',
    )


@pytest.fixture
def dependencies():
    """Создаёт изолированные зависимости исторического ETL."""
    loader = MagicMock()
    transformer = MagicMock()

    loader.get_last_loaded_date.return_value = None
    loader.start_run.side_effect = [101, 102, 103]
    loader.save_historical_period.return_value = 3

    # Минимальные записи для проверки оркестрации.
    transformer.transform_historical_daily.return_value = [
        {'weather_date': date(2026, 1, 1)},
    ]
    transformer.transform_historical_hourly.return_value = [
        {'weather_time': 'test-1'},
        {'weather_time': 'test-2'},
    ]

    return loader, transformer


@pytest.fixture
def mocked_pipeline():
    """Подменяет внешние зависимости исторического ETL."""
    with (
        patch('weather_analytics.etl.pipeline.OpenMeteoClient'),
        patch(
            'weather_analytics.etl.pipeline.WeatherExtractor'
        ) as extractor_class,
        patch(
            'weather_analytics.etl.pipeline.validate_historical_records'
        ) as validator,
    ):
        extractor = extractor_class.return_value
        extractor.extract_historical.return_value = {
            'daily': {},
            'hourly': {},
        }

        yield extractor, validator


def test_historical_pipeline_splits_months(
    location: Location,
    dependencies,
    mocked_pipeline,
) -> None:
    """Проверяет помесячную загрузку и сохранение исторических данных."""
    loader, transformer = dependencies
    extractor, validator = mocked_pipeline

    WeatherETL()._run_historical(
        loader,
        transformer,
        location,
        1,
        date(2026, 1, 15),
        date(2026, 3, 10),
    )

    expected_periods = [
        (date(2026, 1, 15), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 10)),
    ]

    # Проверяем периоды запросов к API и валидации.
    assert [
        item.args[1:]
        for item in extractor.extract_historical.call_args_list
    ] == expected_periods

    assert [
        item.args[1:3]
        for item in validator.call_args_list
    ] == expected_periods

    # Каждый месяц сохраняется отдельной транзакцией.
    assert loader.save_historical_period.call_args_list == [
        call(
            city_id=1,
            run_id=101,
            daily_records=transformer.transform_historical_daily.return_value,
            hourly_records=transformer.transform_historical_hourly.return_value,
            loaded_date=date(2026, 1, 31),
        ),
        call(
            city_id=1,
            run_id=102,
            daily_records=transformer.transform_historical_daily.return_value,
            hourly_records=transformer.transform_historical_hourly.return_value,
            loaded_date=date(2026, 2, 28),
        ),
        call(
            city_id=1,
            run_id=103,
            daily_records=transformer.transform_historical_daily.return_value,
            hourly_records=transformer.transform_historical_hourly.return_value,
            loaded_date=date(2026, 3, 10),
        ),
    ]


def test_historical_pipeline_stops_after_error(
    location: Location,
    dependencies,
    mocked_pipeline,
) -> None:
    """Проверяет остановку исторического ETL после ошибки API."""
    loader, transformer = dependencies
    extractor, validator = mocked_pipeline

    extractor.extract_historical.side_effect = [
        {'daily': {}, 'hourly': {}},
        ConnectionError('Исторический API недоступен'),
    ]

    with pytest.raises(
        ConnectionError,
        match='Исторический API недоступен',
    ):
        WeatherETL()._run_historical(
            loader,
            transformer,
            location,
            1,
            date(2026, 1, 1),
            date(2026, 3, 31),
        )

    # Январь сохраняется, февраль завершается ошибкой.
    # Март не должен запускаться.
    assert extractor.extract_historical.call_count == 2
    validator.assert_called_once()
    loader.save_historical_period.assert_called_once()

    assert (
        loader.save_historical_period.call_args.kwargs['loaded_date']
        == date(2026, 1, 31)
    )

    loader.fail_run.assert_called_once()
    assert loader.fail_run.call_args.args[0] == 102


def test_historical_pipeline_resumes_from_saved_date(
    location: Location,
    dependencies,
    mocked_pipeline,
) -> None:
    """Проверяет возобновление загрузки после сохранённого месяца."""
    loader, transformer = dependencies
    extractor, validator = mocked_pipeline

    loader.get_last_loaded_date.return_value = date(2026, 1, 31)

    WeatherETL()._run_historical(
        loader,
        transformer,
        location,
        1,
        date(2026, 1, 1),
        date(2026, 3, 31),
    )

    # Уже загруженный январь пропускается.
    assert [
        item.args[1:]
        for item in extractor.extract_historical.call_args_list
    ] == [
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 31)),
    ]

    assert validator.call_count == 2

    assert [
        item.kwargs['loaded_date']
        for item in loader.save_historical_period.call_args_list
    ] == [
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]


def test_historical_pipeline_skips_completed_period(
    location: Location,
    dependencies,
    mocked_pipeline,
) -> None:
    """Проверяет пропуск полностью загруженного периода."""
    loader, transformer = dependencies
    extractor, validator = mocked_pipeline

    loader.get_last_loaded_date.return_value = date(2026, 3, 31)

    WeatherETL()._run_historical(
        loader,
        transformer,
        location,
        1,
        date(2026, 1, 1),
        date(2026, 3, 31),
    )

    extractor.extract_historical.assert_not_called()
    validator.assert_not_called()
    loader.start_run.assert_not_called()
    loader.save_historical_period.assert_not_called()


def test_historical_pipeline_rejects_incomplete_data(
    location: Location,
    dependencies,
    mocked_pipeline,
) -> None:
    """Проверяет отказ от сохранения неполных исторических данных."""
    loader, transformer = dependencies
    extractor, validator = mocked_pipeline

    # В этом тесте используем настоящий валидатор.
    # Остальные внешние зависимости остаются подменёнными.
    validator.side_effect = validate_historical_records

    # За два дня ожидаются две суточные и 48 почасовых записей.
    # Трансформер возвращает одну суточную и две почасовые.
    with pytest.raises(
        ValueError,
        match='Неполные или некорректные суточные данные',
    ):
        WeatherETL()._run_historical(
            loader,
            transformer,
            location,
            1,
            date(2026, 1, 1),
            date(2026, 1, 2),
        )

    # Ошибка валидации не должна приводить к сохранению.
    loader.save_historical_period.assert_not_called()

    # Запуск должен быть зарегистрирован как неуспешный.
    loader.fail_run.assert_called_once()
    assert loader.fail_run.call_args.args[0] == 101

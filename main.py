"""Точка входа ETL-приложения Stormy."""

import argparse
from datetime import date, timedelta

from weather_analytics.config import get_settings
from weather_analytics.etl.pipeline import WeatherETL
from weather_analytics.logging_config import StormyLogger


def parse_args() -> argparse.Namespace:
    """Читает параметры запуска ETL из командной строки."""
    parser = argparse.ArgumentParser(
        description='Загрузка погодных данных Stormy.',
    )
    parser.add_argument(
        '--mode',
        choices=('local', 'initial', 'daily', 'forecast', 'batch'),
        default='local',
        help='Режим выполнения ETL.',
    )
    parser.add_argument(
        '--start-date',
        type=date.fromisoformat,
        help='Начальная дата в формате YYYY-MM-DD.',
    )
    parser.add_argument(
        '--end-date',
        type=date.fromisoformat,
        help='Конечная дата в формате YYYY-MM-DD.',
    )
    parser.add_argument(
        '--cities',
        nargs='+',
        help='Названия городов из справочника.',
    )
    parser.add_argument(
        '--max-periods',
        type=int,
        help='Максимум месячных периодов за весь запуск.',
    )
    return parser.parse_args()


def main() -> None:
    """Настраивает логирование и запускает выбранный ETL."""
    StormyLogger()

    args = parse_args()
    settings = get_settings()

    if args.mode != 'local' and settings.app_env != 'server':
        raise ValueError('Серверные режимы ETL доступны только при APP_ENV=server')

    if args.mode == 'local' and settings.app_env != 'local':
        raise ValueError('Локальный режим ETL доступен только при APP_ENV=local')

    if args.max_periods is not None and args.max_periods < 1:
        raise ValueError('--max-periods должен быть положительным числом')

    # Ручные ограничения разрешены только в серверном режиме batch.
    if args.mode != 'batch' and any(
        value is not None
        for value in (
            args.start_date,
            args.end_date,
            args.cities,
            args.max_periods,
        )
    ):
        raise ValueError(
            'Параметры дат, городов и лимита доступны только для --mode batch'
        )

    etl = WeatherETL()

    if args.mode == 'local':
        etl.run(
            mode='local',
            city_names=settings.etl_local_cities,
            start_date=settings.etl_local_start_date,
            end_date=settings.etl_local_end_date,
        )
        return

    if args.mode == 'forecast':
        etl.run(mode='forecast')
        return

    if args.mode == 'batch':
        if args.start_date is None or args.end_date is None:
            raise ValueError('Для batch обязательны --start-date и --end-date')

        if args.max_periods is None:
            raise ValueError('Для batch обязателен --max-periods')

        etl.run(
            mode='batch',
            city_names=tuple(args.cities) if args.cities else None,
            start_date=args.start_date,
            end_date=args.end_date,
            max_periods=args.max_periods,
        )
        return

    # Для архива используем запас в пять дней.
    end_date = date.today() - timedelta(days=5)

    etl.run(
        mode=args.mode,
        start_date=settings.etl_history_start_date,
        end_date=end_date,
    )


if __name__ == '__main__':
    main()

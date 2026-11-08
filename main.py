"""Точка входа ETL-приложения Stormy."""

import argparse
import logging
from datetime import date, timedelta

from weather_analytics.config import get_settings
from weather_analytics.etl.pipeline import WeatherETL


def parse_args() -> argparse.Namespace:
    """Читает режим запуска ETL из командной строки."""
    parser = argparse.ArgumentParser(
        description='Загрузка погодных данных Stormy.',
    )
    parser.add_argument(
        '--mode',
        choices=('local', 'initial', 'daily', 'forecast'),
        default='local',
        help='Режим выполнения ETL.',
    )
    return parser.parse_args()


def main() -> None:
    """Настраивает логирование и запускает выбранный ETL."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
    )

    args = parse_args()
    settings = get_settings()

    # Не допускаем массовую серверную загрузку в локальной среде.
    if args.mode != 'local' and settings.app_env != 'server':
        raise ValueError('Серверные режимы ETL доступны только при APP_ENV=server')

    if args.mode == 'local' and settings.app_env != 'local':
        raise ValueError('Локальный режим ETL доступен только при APP_ENV=local')

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

    # Для архива используем консервативный запас в пять дней.
    # Это значение позже можно вынести в настройки при необходимости.
    end_date = date.today() - timedelta(days=5)

    etl.run(
        mode=args.mode,
        start_date=settings.etl_history_start_date,
        end_date=end_date,
    )


if __name__ == '__main__':
    main()

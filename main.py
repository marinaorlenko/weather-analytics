"""Точка входа приложения Weather Analytics."""

import logging

from weather_analytics.etl.pipeline import WeatherETL


def main() -> None:
    """Настраивает логирование и запускает погодный ETL."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
    )

    # Вся логика ETL находится в отдельном классе.
    etl = WeatherETL()
    etl.run()


if __name__ == '__main__':
    main()

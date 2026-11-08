"""Управление журналом ETL-запусков и состоянием исторической загрузки.

Модуль отвечает за регистрацию запусков, их завершение,
фиксацию ошибок и хранение последней загруженной даты.

Транзакционное сохранение погодных данных и связанных с ними
статусов выполняется в основном WeatherLoader.
"""

import logging
from datetime import date

import psycopg

from weather_analytics.config import ConnectionParams

logger = logging.getLogger(__name__)


class ETLRunRepository:
    """Работает с таблицами etl_runs и etl_state в PostgreSQL."""

    def __init__(self, connection_params: ConnectionParams) -> None:
        """Принимает параметры подключения к PostgreSQL.

        Args:
            connection_params: Параметры подключения для psycopg.
        """
        self.connection_params = connection_params

    def start_run(self, pipeline: str) -> int:
        """Регистрирует начало ETL-запуска и возвращает его идентификатор.

        Args:
            pipeline: Название ETL-процесса.

        Returns:
            Идентификатор созданного запуска.

        Raises:
            ValueError: Если название процесса пустое.
            RuntimeError: Если PostgreSQL не вернул идентификатор запуска.
        """
        if not pipeline.strip():
            raise ValueError('Название ETL-процесса не может быть пустым')

        query = """
            INSERT INTO etl_runs (
                pipeline,
                started_at,
                status,
                rows_loaded
            )
            VALUES (
                %(pipeline)s,
                CURRENT_TIMESTAMP,
                'running',
                0
            )
            RETURNING run_id;
        """

        # Создаём запись о запуске в отдельной транзакции.
        # Она должна существовать до начала загрузки данных.
        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    {'pipeline': pipeline},
                )
                result = cursor.fetchone()

                if result is None:
                    raise RuntimeError('Не удалось получить идентификатор ETL-запуска')

                run_id = result[0]

        logger.info(
            'ETL-запуск зарегистрирован: pipeline=%s, run_id=%s',
            pipeline,
            run_id,
        )

        return run_id

    def finish_run(self, run_id: int, rows_loaded: int) -> None:
        """Регистрирует успешное завершение активного ETL-запуска.

        Args:
            run_id: Идентификатор ETL-запуска.
            rows_loaded: Количество загруженных записей.

        Raises:
            ValueError: Если количество записей отрицательное
                или активный запуск не найден.
        """
        if rows_loaded < 0:
            raise ValueError(
                'Количество загруженных записей не может быть отрицательным'
            )

        query = """
            UPDATE etl_runs
            SET
                finished_at = CURRENT_TIMESTAMP,
                status = 'success',
                rows_loaded = %(rows_loaded)s,
                error_message = NULL
            WHERE run_id = %(run_id)s
              AND status = 'running'
            RETURNING run_id;
        """

        # Завершаем только запуск, который ещё выполняется.
        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    {
                        'run_id': run_id,
                        'rows_loaded': rows_loaded,
                    },
                )

                if cursor.fetchone() is None:
                    raise ValueError(f'Активный ETL-запуск с run_id={run_id} не найден')

        logger.info(
            'ETL-запуск завершён: run_id=%s, записей=%s',
            run_id,
            rows_loaded,
        )

    def fail_run(self, run_id: int, error: Exception) -> None:
        """Фиксирует ошибку и завершает активный ETL-запуск.

        Args:
            run_id: Идентификатор ETL-запуска.
            error: Исключение, вызвавшее сбой.

        Raises:
            ValueError: Если активный запуск не найден.
        """
        query = """
            UPDATE etl_runs
            SET
                finished_at = CURRENT_TIMESTAMP,
                status = 'failed',
                error_message = %(error_message)s
            WHERE run_id = %(run_id)s
              AND status = 'running'
            RETURNING run_id;
        """

        # Ошибка записывается отдельной транзакцией,
        # поскольку основная транзакция загрузки могла откатиться.
        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    {
                        'run_id': run_id,
                        'error_message': str(error),
                    },
                )

                if cursor.fetchone() is None:
                    raise ValueError(f'Активный ETL-запуск с run_id={run_id} не найден')

        logger.error(
            'ETL-запуск завершился с ошибкой: run_id=%s, ошибка=%s',
            run_id,
            error,
        )

    def get_last_loaded_date(self, city_id: int) -> date | None:
        """Возвращает последнюю успешно загруженную историческую дату.

        Args:
            city_id: Идентификатор города.

        Returns:
            Последняя дата загрузки либо None для нового города.
        """
        query = """
            SELECT last_loaded_date
            FROM etl_state
            WHERE pipeline = 'historical'
              AND city_id = %s;
        """

        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (city_id,))
                result = cursor.fetchone()

        # У нового города запись о прогрессе ещё отсутствует.
        return result[0] if result else None

    def update_last_loaded_date(
        self,
        city_id: int,
        loaded_date: date,
    ) -> None:
        """Обновляет последнюю успешно загруженную историческую дату.

        Args:
            city_id: Идентификатор города.
            loaded_date: Дата завершённого исторического периода.
        """
        query = """
            INSERT INTO etl_state (
                pipeline,
                city_id,
                last_loaded_date,
                last_loaded_at
            )
            VALUES ('historical', %s, %s, NOW())
            ON CONFLICT (pipeline, city_id)
            DO UPDATE SET
                last_loaded_date = GREATEST(
                    etl_state.last_loaded_date,
                    EXCLUDED.last_loaded_date
                ),
                last_loaded_at = NOW(),
                updated_at = NOW();
        """

        # Отдельный метод предназначен для самостоятельного
        # обновления состояния вне составной операции загрузки.
        with psycopg.connect(**self.connection_params) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (city_id, loaded_date),
                )

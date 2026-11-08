"""Подготовка и пакетное выполнение SQL-запросов для погодных данных.

Модуль содержит универсальные операции INSERT ... ON CONFLICT.
Управление подключениями и транзакциями остаётся в WeatherLoader.
"""

from typing import Any

from psycopg import Cursor, sql


def build_upsert_query(
    table: str,
    columns: tuple[str, ...],
    conflict_columns: tuple[str, ...],
    forecast: bool = False,
) -> sql.Composed:
    """Формирует параметризованный SQL-запрос вставки с обновлением.

    Args:
        table: Название таблицы PostgreSQL.
        columns: Столбцы погодных показателей.
        conflict_columns: Столбцы уникального ограничения.
        forecast: Признак прогнозной таблицы.

    Returns:
        SQL-запрос INSERT ... ON CONFLICT DO UPDATE.
    """
    # Для прогнозных таблиц дополнительно сохраняем идентификатор
    # конкретного ETL-запуска, сформировавшего прогноз.
    insert_columns = (
        ('city_id', 'forecast_run_id', *columns) if forecast else ('city_id', *columns)
    )

    # Ключевые столбцы конфликта не обновляем.
    # Остальные значения заменяем новыми из EXCLUDED.
    update_columns = tuple(
        column
        for column in insert_columns
        if column not in ('city_id', *conflict_columns)
    )

    # Имена таблиц и столбцов передаём через Identifier,
    # а значения — через именованные Placeholder.
    return sql.SQL(
        'INSERT INTO {table} ({columns}) '
        'VALUES ({values}) '
        'ON CONFLICT ({conflict}) '
        'DO UPDATE SET {updates}'
    ).format(
        table=sql.Identifier(table),
        columns=sql.SQL(', ').join(sql.Identifier(column) for column in insert_columns),
        values=sql.SQL(', ').join(sql.Placeholder(column) for column in insert_columns),
        conflict=sql.SQL(', ').join(
            sql.Identifier(column) for column in conflict_columns
        ),
        updates=sql.SQL(', ').join(
            sql.SQL('{} = EXCLUDED.{}').format(
                sql.Identifier(column),
                sql.Identifier(column),
            )
            for column in update_columns
        ),
    )


def prepare_records(
    city_id: int,
    records: list[dict[str, Any]],
    columns: tuple[str, ...],
    forecast_run_id: int | None = None,
) -> list[dict[str, Any]]:
    """Подготавливает погодные записи для пакетной загрузки.

    Args:
        city_id: Идентификатор города в PostgreSQL.
        records: Преобразованные погодные записи.
        columns: Разрешённые столбцы таблицы.
        forecast_run_id: Идентификатор прогнозного ETL-запуска.

    Returns:
        Список словарей с параметрами SQL-запросов.
    """
    params: list[dict[str, Any]] = []

    for record in records:
        # Используем только предусмотренные схемой поля.
        # Отсутствующие показатели передаются как NULL.
        item = {
            'city_id': city_id,
            **{column: record.get(column) for column in columns},
        }

        # Идентификатор запуска необходим только прогнозным таблицам.
        if forecast_run_id is not None:
            item['forecast_run_id'] = forecast_run_id

        params.append(item)

    return params


def execute_batch(
    cursor: Cursor[Any],
    table: str,
    columns: tuple[str, ...],
    conflict_columns: tuple[str, ...],
    params: list[dict[str, Any]],
    forecast: bool = False,
) -> None:
    """Выполняет пакетную вставку или обновление погодных записей.

    Args:
        cursor: Курсор активной транзакции PostgreSQL.
        table: Название целевой таблицы.
        columns: Столбцы погодных показателей.
        conflict_columns: Столбцы уникального ограничения.
        params: Подготовленные параметры запросов.
        forecast: Признак прогнозной таблицы.
    """
    # Пустой набор записей не требует обращения к базе данных.
    if not params:
        return

    query = build_upsert_query(
        table=table,
        columns=columns,
        conflict_columns=conflict_columns,
        forecast=forecast,
    )

    # Используем существующий курсор, чтобы все операции
    # выполнялись внутри транзакции вызывающего компонента.
    cursor.executemany(query, params)

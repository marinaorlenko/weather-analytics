"""Централизованная настройка логирования приложения Stormy.

Модуль настраивает вывод сообщений в консоль и ежедневный лог-файл.
Устаревшие журналы автоматически удаляются после установленного
срока хранения.
"""

import logging
import re
import sys
from datetime import date, timedelta
from pathlib import Path

LOG_DIRECTORY = 'logs'
LOG_RETENTION_DAYS = 14
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class StormyLogger:
    """Управляет обработчиками логирования и хранением журналов."""

    def __init__(
        self,
        log_dir: str | Path = LOG_DIRECTORY,
        retention_days: int = LOG_RETENTION_DAYS,
    ) -> None:
        """Создаёт каталог, очищает старые журналы и настраивает logging."""
        if retention_days < 1:
            raise ValueError('Срок хранения логов должен быть положительным')

        self.log_dir = Path(log_dir)
        self.retention_days = retention_days

        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Удаляем устаревшие файлы перед настройкой обработчиков.
        self._cleanup_logs()
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Настраивает корневой логгер для всех модулей приложения."""
        logger = logging.getLogger()
        logger.setLevel(LOG_LEVEL)

        formatter = logging.Formatter(
            LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
        )

        # Удаляем старые обработчики, чтобы сообщения не дублировались.
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()

        # Консольный вывод доступен через docker logs и journalctl.
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)

        # Файл содержит сообщения всех модулей приложения за текущий день.
        log_file = self.log_dir / f'etl_{date.today():%Y-%m-%d}.log'

        file_handler = logging.FileHandler(
            log_file,
            encoding='utf-8',
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        # Снижаем подробность технических сообщений HTTP-клиента.
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)

    def _cleanup_logs(self) -> None:
        """Удаляет ежедневные журналы старше срока хранения."""
        cutoff = date.today() - timedelta(days=self.retention_days - 1)

        # Не затрагиваем файлы, не соответствующие формату etl_YYYY-MM-DD.log.
        for log_file in self.log_dir.glob('etl_*.log'):
            if not re.fullmatch(r'etl_\d{4}-\d{2}-\d{2}\.log', log_file.name):
                continue

            try:
                file_date = date.fromisoformat(log_file.stem.removeprefix('etl_'))
            except ValueError:
                continue

            if file_date < cutoff:
                try:
                    log_file.unlink()
                except OSError:
                    logging.getLogger(__name__).warning(
                        'Не удалось удалить устаревший журнал: %s',
                        log_file,
                        exc_info=True,
                    )

"""Логгер проекта: цветной вывод в консоль (INFO+) и файловый DEBUG-лог на сессию parser/publisher."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

LOGS_DIR_NAME = "logs"

_LOG_FORMAT = "[%(asctime)s] | (%(module)s:%(funcName)s:%(lineno)d) -- %(levelname)s -- %(message)s"
_LOG_DATEFMT = "%H:%M:%S"
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%S"

ModuleName = Literal["parser", "publisher"]


class _ConsoleColorFormatter(logging.Formatter):
    """Красит WARNING жёлтым, ERROR/CRITICAL красным при выводе в TTY."""

    _YELLOW = "\033[33m"
    _RED = "\033[31m"
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Форматирует запись лога, окрашивая WARNING/ERROR/CRITICAL при выводе в TTY.

        Args:
            record: Запись лога, переданная стандартным механизмом logging.

        Returns:
            Отформатированная строка, обёрнутая в ANSI-код цвета для WARNING/ERROR/CRITICAL.
        """
        formatted = super().format(record)
        if not sys.stderr.isatty():
            return formatted
        if record.levelno >= logging.ERROR:
            return f"{self._RED}{formatted}{self._RESET}"
        if record.levelno == logging.WARNING:
            return f"{self._YELLOW}{formatted}{self._RESET}"
        return formatted


def _get_stream_handler() -> logging.StreamHandler:
    """
    Создаёт консольный обработчик уровня INFO с цветным форматированием.

    Returns:
        Настроенный StreamHandler.
    """
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(_ConsoleColorFormatter(fmt=_LOG_FORMAT, datefmt=_LOG_DATEFMT))
    return handler


def _get_file_handler(module_name: ModuleName, logs_dir: Path) -> logging.FileHandler:
    """
    Создаёт файловый обработчик уровня DEBUG для текущей сессии запуска.

    Args:
        module_name: Имя модуля ("parser" или "publisher") — используется в имени файла.
        logs_dir: Директория для лог-файлов; создаётся, если отсутствует.

    Returns:
        Настроенный FileHandler, пишущий в файл с именем "{module_name}-{timestamp}.log".
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime(_TIMESTAMP_FORMAT)
    handler = logging.FileHandler(logs_dir / f"{module_name}-{timestamp}.log", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_LOG_DATEFMT))
    return handler


def setup_logging(
    logger_name: str = "doc_parser",
    module_name: ModuleName | None = None,
    logs_dir: Path | None = None,
) -> logging.Logger:
    """
    Настраивает логгер с консольным обработчиком и опционально файловым логом сессии.

    Консольный обработчик добавляется один раз на имя логгера. Если переданы
    module_name и logs_dir, дополнительно подключается файловый DEBUG-обработчик
    текущей сессии для parser/publisher, снимая предыдущий файловый обработчик,
    если он был.

    Args:
        logger_name: Имя логгера.
        module_name: Имя модуля ("parser" или "publisher"), если нужен файловый лог сессии.
        logs_dir: Директория для лог-файлов; обязателен вместе с module_name.

    Returns:
        Настроенный экземпляр logging.Logger.
    """
    log = logging.getLogger(logger_name)

    if not log.handlers:
        log.setLevel(logging.DEBUG)
        log.addHandler(_get_stream_handler())

    if module_name is not None and logs_dir is not None:
        for handler in list(log.handlers):
            if isinstance(handler, logging.FileHandler):
                log.removeHandler(handler)
        log.addHandler(_get_file_handler(module_name, logs_dir))

    return log


def clear_logs_dir(logs_dir: Path) -> list[Path]:
    """
    Удаляет все файлы логов из директории логов.

    Args:
        logs_dir: Директория с логами.

    Returns:
        Список удалённых путей (пустой, если директории нет или удалять нечего).
    """
    if not logs_dir.exists():
        return []
    deleted = sorted(logs_dir.glob("*.log"))
    for path in deleted:
        path.unlink()
    return deleted


logger = setup_logging()

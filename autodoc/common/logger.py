"""
Централизованный логгер проекта.

Предоставляет единственный настроенный экземпляр ``logger`` для использования
во всех модулях проекта. Консоль показывает INFO и выше (WARNING — жёлтым,
ERROR/CRITICAL — красным); дополнительно каждый запуск parser/publisher может
подключить файловый обработчик уровня DEBUG в ``logs/`` (см.
``start_session_file_log``).
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

LOGS_DIR_NAME: str = "logs"

_CONSOLE_FORMAT: str = (
    "[%(asctime)s] | (%(module)s:%(funcName)s:%(lineno)d) -- %(levelname)s -- %(message)s"
)
_CONSOLE_DATEFMT: str = "%H:%M:%S"

_FILE_FORMAT: str = (
    "[%(asctime)s] | (%(module)s:%(funcName)s:%(lineno)d) -- %(levelname)s -- %(message)s"
)
_FILE_DATEFMT: str = "%Y-%m-%d %H:%M:%S"

_FILENAME_TIMESTAMP_FORMAT: str = "%Y-%m-%dT%H-%M-%S"

ModuleName = Literal["parser", "publisher"]


class _ConsoleColorFormatter(logging.Formatter):
    """Формирует цветную строку лога для консоли.

    Раскрашивает предупреждения и ошибки, чтобы их было проще заметить среди
    обычного вывода, не меняя формат самой записи.
    """

    _YELLOW = "\033[33m"
    _RED = "\033[31m"
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
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


def setup_logging(logger_name: str = "doc_parser") -> logging.Logger:
    """
    Настраивает логгер с выводом модуля и функции.

    Args:
        logger_name: Имя логгера.

    Returns:
        Настроенный экземпляр logging.Logger.
    """
    log = logging.getLogger(logger_name)

    if not log.handlers:
        log.setLevel(logging.DEBUG)

        console_formatter = _ConsoleColorFormatter(fmt=_CONSOLE_FORMAT, datefmt=_CONSOLE_DATEFMT)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)

        log.addHandler(console_handler)

    return log


def start_session_file_log(
    logger_obj: logging.Logger,
    module_name: ModuleName,
    logs_dir: Path,
) -> Callable[[], None]:
    """Подключает к логгеру файловый обработчик уровня DEBUG для текущего запуска.

    Args:
        logger_obj: Логгер, к которому нужно подключить файловый обработчик.
        module_name: Имя модуля ("parser" или "publisher") — используется в имени файла.
        logs_dir: Директория для лог-файлов; создаётся, если отсутствует.

    Returns:
        Функция без аргументов для закрытия обработчика по завершении запуска
        (используется через ``ctx.call_on_close`` — см. ``cli/app.py``).
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime(_FILENAME_TIMESTAMP_FORMAT)
    log_path = logs_dir / f"{module_name}-{timestamp}.log"

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt=_FILE_FORMAT, datefmt=_FILE_DATEFMT))
    logger_obj.addHandler(file_handler)

    def close() -> None:
        """Отключает и закрывает файловый обработчик текущего запуска."""
        logger_obj.removeHandler(file_handler)
        file_handler.close()

    return close


def clear_logs_dir(logs_dir: Path) -> list[Path]:
    """Удаляет все файлы логов из директории логов.

    Args:
        logs_dir: Директория с логами.

    Returns:
        Список удалённых путей (пустой, если директории нет или удалять нечего).
    """
    if not logs_dir.exists():
        return []
    deleted: list[Path] = []
    for path in sorted(logs_dir.glob("*.log")):
        path.unlink()
        deleted.append(path)
    return deleted


logger = setup_logging()

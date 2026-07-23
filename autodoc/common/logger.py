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
        formatted = super().format(record)
        if not sys.stderr.isatty():
            return formatted
        if record.levelno >= logging.ERROR:
            return f"{self._RED}{formatted}{self._RESET}"
        if record.levelno == logging.WARNING:
            return f"{self._YELLOW}{formatted}{self._RESET}"
        return formatted


def _get_stream_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(_ConsoleColorFormatter(fmt=_LOG_FORMAT, datefmt=_LOG_DATEFMT))
    return handler


def _get_file_handler(module_name: ModuleName, logs_dir: Path) -> logging.FileHandler:
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
    """Настраивает логгер: консольный обработчик (один раз) + опционально файловый
    DEBUG-лог текущей сессии для parser/publisher (если переданы module_name и logs_dir)."""
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
    """Удаляет все *.log файлы из директории логов, возвращает список удалённых путей."""
    if not logs_dir.exists():
        return []
    deleted = sorted(logs_dir.glob("*.log"))
    for path in deleted:
        path.unlink()
    return deleted


logger = setup_logging()

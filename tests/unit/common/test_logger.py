"""Модульные тесты для autodoc/common/logger.py.

Тестируем только собственный код модуля (выбор имени логгера по умолчанию,
поддержку кастомного имени, очистку директории логов) — не поведение самого
``logging``, которое уже протестировано в стандартной библиотеке.
"""

import logging
from pathlib import Path

import pytest

from autodoc.common.logger import clear_logs_dir, logger, setup_logging

_DEFAULT_NAME: str = "doc_parser"


@pytest.fixture
def _isolated_logger_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Изолирует реестр логгеров ``logging.Logger.manager.loggerDict`` на время теста.

    ``logging.getLogger(name)`` кеширует инстансы в этом реестре (обычный
    dict) на уровне процесса. Подменяем его копией через ``monkeypatch`` —
    после теста реестр откатывается к исходному состоянию автоматически, без
    ручного перебора хендлеров созданных логгеров.
    """
    monkeypatch.setattr(
        logging.Logger.manager, "loggerDict", dict(logging.Logger.manager.loggerDict)
    )


@pytest.mark.infrastructure
def test_module_level_logger_uses_default_name() -> None:
    """Модуль экспортирует готовый синглтон ``logger`` с именем 'doc_parser' —
    именно этот логгер импортируется во всех остальных модулях проекта."""
    assert logger.name == _DEFAULT_NAME


@pytest.mark.infrastructure
def test_setup_logging_without_argument_defaults_to_doc_parser(
    _isolated_logger_registry: None,
) -> None:
    """Вызов setup_logging() без аргумента настраивает логгер с именем 'doc_parser'."""
    log = setup_logging()

    assert log.name == _DEFAULT_NAME


@pytest.mark.infrastructure
def test_setup_logging_honors_custom_logger_name(_isolated_logger_registry: None) -> None:
    """setup_logging(logger_name=...) — официальный способ получить именованный
    логгер под другим именем (например, для отдельного подпроцесса или инструмента);
    имя результата должно совпадать с переданным, а не с именем по умолчанию."""
    log = setup_logging("autodoc.custom.tool")

    assert log.name == "autodoc.custom.tool"


@pytest.mark.infrastructure
def test_clear_logs_dir_deletes_log_files_and_returns_their_paths(tmp_path: Path) -> None:
    """clear_logs_dir() удаляет все *.log файлы из существующей директории
    и возвращает список фактически удалённых путей."""
    log1 = tmp_path / "a.log"
    log2 = tmp_path / "b.log"
    other = tmp_path / "keep.txt"
    log1.write_text("log a", encoding="utf-8")
    log2.write_text("log b", encoding="utf-8")
    other.write_text("not a log", encoding="utf-8")

    deleted = clear_logs_dir(tmp_path)

    assert set(deleted) == {log1, log2}
    assert not log1.exists()
    assert not log2.exists()
    assert other.exists()  # файлы, не подпадающие под *.log, не трогаются


@pytest.mark.infrastructure
def test_clear_logs_dir_missing_directory_returns_empty_list(tmp_path: Path) -> None:
    """clear_logs_dir() для несуществующей директории возвращает пустой список,
    а не бросает исключение — вызывающий код может передавать директорию логов,
    ещё не созданную setup_logging() при первом запуске."""
    missing_dir = tmp_path / "does_not_exist"

    deleted = clear_logs_dir(missing_dir)

    assert deleted == []


"""
Модульные тесты для autodoc/common/logger.py.

Тестируем только собственный код модуля: единственную условную логику
setup_logging (``if not log.handlers: ...`` — настройка происходит один раз
и не дублируется при повторном вызове) и отдельную функцию clear_logs_dir.
Явно НЕ тестируем то, что переданное имя логгера долетает до
``logging.Logger.name`` — это поведение самого ``logging.getLogger``,
а не код проекта.
"""

import logging
from pathlib import Path
from unittest.mock import Mock

import pytest

from autodoc.common import logger as logger_module
from autodoc.common.logger import clear_logs_dir, setup_logging


@pytest.fixture
def isolated_logger_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Изолирует реестр логгеров ``logging.Logger.manager.loggerDict`` на время теста.

    ``logging.getLogger(name)`` кеширует инстансы в этом реестре (обычный
    dict) на уровне процесса. Подменяем его копией через ``monkeypatch`` —
    после теста реестр откатывается к исходному состоянию автоматически, без
    ручного перебора хендлеров созданных логгеров.
    """
    monkeypatch.setattr(
        logging.Logger.manager, "loggerDict", dict(logging.Logger.manager.loggerDict)
    )


@pytest.mark.infrastructure
@pytest.mark.usefixtures("isolated_logger_registry")
def test_setup_logging_configures_console_handler_only_once() -> None:
    """
    setup_logging() навешивает ровно один консольный обработчик уровня
    INFO на логгер уровня DEBUG при первом вызове; повторный вызов для того
    же имени не добавляет второй обработчик.

    Это единственная содержательная ветка в модуле (``if not log.handlers``),
    которую стоит тестировать: без неё каждая запись лога дублировалась бы в
    выводе при повторной настройке того же логгера.
    """
    log = setup_logging("autodoc.handler-guard.test")

    assert log.level == logging.DEBUG
    assert len(log.handlers) == 1
    assert log.handlers[0].level == logging.INFO

    setup_logging("autodoc.handler-guard.test")

    assert len(log.handlers) == 1


@pytest.mark.infrastructure
@pytest.mark.usefixtures("isolated_logger_registry")
def test_setup_logging_replaces_stale_file_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Повторный вызов setup_logging с module_name/logs_dir на одном логгере не
    копит файловые обработчики: старый снимается перед добавлением нового,
    лог пишется только в актуальный файл. Консольный обработчик при этом не
    трогается и не дублируется.

    Такой повторный вызов не происходит в реальном CLI (parse/publish — это
    отдельные процессы со своим чистым логгером); здесь он смоделирован
    намеренно, чтобы проверить идемпотентность самой функции.

    Таймстемп в имени файла фиксируется явно (два разных значения), а не
    берётся из реального времени: у формата секундная точность, и два вызова
    подряд иначе рискуют получить одно и то же имя файла — тогда проверка
    "запись попала только в один файл" была бы не показательной (файл был бы
    просто один, а не то, что второй не тронут).
    """
    fake_datetime = Mock()
    fake_datetime.now.side_effect = [
        Mock(strftime=Mock(return_value="2026-01-01T12-00-00")),
        Mock(strftime=Mock(return_value="2026-01-01T12-00-01")),
    ]
    monkeypatch.setattr(logger_module, "datetime", fake_datetime)

    log = setup_logging("autodoc.session-file-log.test")

    setup_logging("autodoc.session-file-log.test", module_name="parser", logs_dir=tmp_path)
    setup_logging("autodoc.session-file-log.test", module_name="parser", logs_dir=tmp_path)

    file_handlers = [h for h in log.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1, "старый файловый обработчик должен быть снят"
    assert (
        sum(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in log.handlers
        )
        == 1
    ), "консольный обработчик не должен дублироваться"

    log.info("marker message")
    log_files = sorted(tmp_path.glob("*.log"))
    assert len(log_files) == 2, "должно быть два файла сессии — от первого и второго вызова"

    written_to = [p for p in log_files if "marker message" in p.read_text(encoding="utf-8")]
    assert len(written_to) == 1, "запись должна попасть только в актуальный файл сессии"


@pytest.mark.infrastructure
def test_clear_logs_dir_deletes_log_files_and_returns_their_paths(tmp_path: Path) -> None:
    """
    clear_logs_dir() удаляет все *.log файлы из существующей директории
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
    """
    clear_logs_dir() для несуществующей директории возвращает пустой список,
    а не бросает исключение — вызывающий код может передавать директорию логов,
    ещё не созданную setup_logging() при первом запуске."""
    missing_dir = tmp_path / "does_not_exist"

    deleted = clear_logs_dir(missing_dir)

    assert deleted == []

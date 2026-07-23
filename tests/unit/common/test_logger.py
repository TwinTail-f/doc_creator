"""Модульные тесты для autodoc/common/logger.py.

Тестируем только собственный код модуля: единственную условную логику
setup_logging (``if not log.handlers: ...`` — настройка происходит один раз
и не дублируется при повторном вызове) и отдельную функцию clear_logs_dir.
Явно НЕ тестируем то, что переданное имя логгера долетает до
``logging.Logger.name`` — это поведение самого ``logging.getLogger``,
а не код проекта.
"""

import logging
from pathlib import Path

import pytest

from autodoc.common.logger import clear_logs_dir, setup_logging, start_session_file_log


@pytest.fixture
def isolated_logger_registry(monkeypatch: pytest.MonkeyPatch) -> None:
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
@pytest.mark.usefixtures("isolated_logger_registry")
def test_setup_logging_configures_console_handler_only_once() -> None:
    """setup_logging() навешивает ровно один консольный обработчик уровня
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
def test_start_session_file_log_replaces_stale_handler_without_close(
    tmp_path: Path,
) -> None:
    """Повторный вызов start_session_file_log без закрытия предыдущего запуска
    не копит файловые обработчики, а снимает старый перед добавлением нового.

    Бизнес-правило:
        start_session_file_log идемпотентна так же, как setup_logging: даже
        если предыдущая сессия не была явно закрыта, обработчики от разных
        запусков не накапливаются на одном логгере, и запись лога не
        дублируется в старые файлы.

    Предусловия:
        - Чистый логгер без обработчиков (session-scoped fixture).

    Шаги:
        1. Дважды вызвать start_session_file_log на одном логгере.
        2. Записать одну запись лога.

    Ожидаемый результат:
        - На логгере остаётся ровно один файловый обработчик (плюс консольный).
        - Запись лога попадает только в файл второго (актуального) запуска.
    """
    log = setup_logging("autodoc.session-file-log.test")

    start_session_file_log(log, "parser", tmp_path)
    start_session_file_log(log, "parser", tmp_path)

    file_handlers = [h for h in log.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1, "старый файловый обработчик должен быть снят"

    log.info("marker message")
    log_files = sorted(tmp_path.glob("*.log"))
    written_to = [p for p in log_files if "marker message" in p.read_text(encoding="utf-8")]
    assert len(written_to) == 1, "запись должна попасть только в актуальный файл сессии"



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

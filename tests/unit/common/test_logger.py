"""Модульные тесты для autodoc/common/logger.py.

Проверяет реальное поведение ``setup_logging``: имя логгера по умолчанию,
что параметр ``logger_name`` действительно позволяет его переопределить
(это официальная возможность API, а не то, чему тест должен препятствовать),
и что повторный вызов для одного и того же имени не плодит дублирующиеся
обработчики.
"""

import logging

import pytest

from autodoc.common.logger import logger, setup_logging

_DEFAULT_NAME: str = "doc_parser"


@pytest.fixture
def _cleanup_logger():
    """Удаляет тестовые логгеры из реестра logging после теста.

    ``logging.getLogger(name)`` кеширует инстансы по имени на уровне процесса,
    поэтому без явной очистки обработчиков логгер, созданный в одном тесте,
    "утечёт" в реестр и может повлиять на последующие тесты.
    """
    created_names: list[str] = []

    def _factory(name: str) -> logging.Logger:
        created_names.append(name)
        return setup_logging(name)

    yield _factory

    for name in created_names:
        log = logging.getLogger(name)
        for handler in list(log.handlers):
            log.removeHandler(handler)
            handler.close()


@pytest.mark.infrastructure
def test_module_level_logger_uses_default_name() -> None:
    """Модуль экспортирует готовый синглтон ``logger`` с именем 'doc_parser' —
    именно этот логгер импортируется во всех остальных модулях проекта."""
    assert logger.name == _DEFAULT_NAME


@pytest.mark.infrastructure
def test_setup_logging_without_argument_defaults_to_doc_parser(_cleanup_logger) -> None:
    """Вызов setup_logging() без аргумента настраивает логгер с именем 'doc_parser'."""
    log = setup_logging()

    assert log.name == _DEFAULT_NAME


@pytest.mark.infrastructure
def test_setup_logging_honors_custom_logger_name(_cleanup_logger) -> None:
    """setup_logging(logger_name=...) — официальный способ получить именованный
    логгер под другим именем (например, для отдельного подпроцесса или инструмента);
    имя результата должно совпадать с переданным, а не с именем по умолчанию."""
    log = _cleanup_logger("autodoc.custom.tool")

    assert log.name == "autodoc.custom.tool"


@pytest.mark.infrastructure
def test_setup_logging_is_idempotent_for_same_name(_cleanup_logger) -> None:
    """Повторный вызов setup_logging() с тем же именем возвращает тот же логгер
    и не добавляет второй обработчик консоли — иначе каждая запись лога
    дублировалась бы в выводе."""
    first_call = _cleanup_logger("autodoc.idempotency.test")
    second_call = setup_logging("autodoc.idempotency.test")

    assert first_call is second_call
    assert len(second_call.handlers) == 1

